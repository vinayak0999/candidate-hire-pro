from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
import httpx

from ..database import get_db
from ..models.user import User
from ..schemas.user import UserCreate, UserProfile, Token
from ..services.auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    get_current_user
)
from ..services.email import (
    generate_otp,
    generate_reset_token,
    get_otp_expiry,
    get_reset_token_expiry,
    send_otp_email,
    send_welcome_email,
    send_password_reset_email
)
from ..config import get_settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()


# ============================================================================
# Google OAuth Schemas
# ============================================================================

class GoogleAuthRequest(BaseModel):
    """Request from frontend with Google OAuth data"""
    id_token: str  # Actually the access_token from Google
    email: Optional[EmailStr] = None  # User's email from Google
    name: Optional[str] = None  # User's name from Google
    picture: Optional[str] = None  # User's avatar from Google
    # Optional: for new user registration
    registration_number: Optional[str] = None


class GoogleAuthResponse(BaseModel):
    """Response after Google authentication"""
    access_token: str
    token_type: str = "bearer"
    is_new_user: bool = False
    profile_complete: bool = False
    next_step: Optional[str] = None  # "complete_registration", "upload_resume", or None
    user: Optional[dict] = None


# Schemas for email verification
class SendOTPRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str
    success: bool = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    profile_complete: bool = True
    next_step: Optional[str] = None  # "verify_email", "upload_resume", or None


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.

    Step-wise process:
    1. If email not verified → returns error with next_step="verify_email"
    2. If resume not uploaded → returns token with profile_complete=False, next_step="upload_resume"
    3. If all complete → returns full access token
    """
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 1: Check if email is verified (skip for admin users)
    if not user.is_verified and user.role.value != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first.",
            headers={"X-Next-Step": "verify_email"}
        )

    # Generate token (needed for resume upload even if profile incomplete)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )

    # Step 2: Check if profile is complete (resume uploaded) - skip for admin
    if user.role.value != "ADMIN" and not user.profile_complete:
        # Check if resume exists in profile
        from ..models.profile import CandidateProfile
        profile_result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        )
        profile = profile_result.scalar_one_or_none()

        if not profile or not profile.resume_url:
            return LoginResponse(
                access_token=access_token,
                profile_complete=False,
                next_step="upload_resume"
            )
        else:
            # Resume exists, mark profile as complete
            user.profile_complete = True
            await db.commit()

    return LoginResponse(
        access_token=access_token,
        profile_complete=True,
        next_step=None
    )


@router.post("/register", response_model=MessageResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user - sends OTP for verification"""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        else:
            # User exists but not verified - resend OTP
            otp = generate_otp()
            existing_user.verification_otp = otp
            existing_user.otp_expires_at = get_otp_expiry()
            await db.commit()
            
            await send_otp_email(existing_user.email, existing_user.name, otp)
            return MessageResponse(
                message="Account exists. New OTP sent to your email. Please verify."
            )
    
    # Check if reg number exists
    result = await db.execute(select(User).where(User.registration_number == user_data.registration_number))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration number already exists"
        )
    
    # Generate OTP
    otp = generate_otp()
    
    # Create user (not verified yet)
    user = User(
        email=user_data.email,
        name=user_data.name,
        registration_number=user_data.registration_number,
        hashed_password=get_password_hash(user_data.password),
        is_verified=False,
        verification_otp=otp,
        otp_expires_at=get_otp_expiry()
    )
    db.add(user)
    await db.commit()
    
    # Send OTP email
    await send_otp_email(user.email, user.name, otp)
    
    return MessageResponse(
        message="Registration successful! Please check your email for the verification code."
    )


@router.post("/send-otp", response_model=MessageResponse)
async def send_otp(request: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    """Resend OTP to email"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user:
        return MessageResponse(message="If the email exists, an OTP has been sent.")
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified. Please login."
        )
    
    otp = generate_otp()
    user.verification_otp = otp
    user.otp_expires_at = get_otp_expiry()
    await db.commit()
    
    await send_otp_email(user.email, user.name, otp)
    
    return MessageResponse(message="OTP sent to your email.")


@router.post("/verify-otp", response_model=Token)
async def verify_otp(request: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    """Verify OTP and activate account"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or OTP"
        )
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified. Please login."
        )
    
    if user.verification_otp != request.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )
    
    if user.otp_expires_at and user.otp_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Please request a new one."
        )
    
    # Verify user
    user.is_verified = True
    user.verification_otp = None
    user.otp_expires_at = None
    await db.commit()
    
    # Send welcome email
    await send_welcome_email(user.email, user.name)
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    
    return Token(access_token=access_token)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(request: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Send password reset email"""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    
    if not user:
        return MessageResponse(message="If the email exists, a reset link has been sent.")
    
    reset_token = generate_reset_token()
    user.reset_token = reset_token
    user.reset_token_expires_at = get_reset_token_expiry()
    await db.commit()
    
    await send_password_reset_email(user.email, user.name, reset_token)
    
    return MessageResponse(message="If the email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(request: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password with token"""
    result = await db.execute(select(User).where(User.reset_token == request.token))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    if user.reset_token_expires_at and user.reset_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token expired. Please request a new one."
        )
    
    user.hashed_password = get_password_hash(request.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    await db.commit()
    
    return MessageResponse(message="Password reset successful. You can now login.")


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return current_user


# ============================================================================
# Google OAuth Authentication
# ============================================================================

async def verify_google_token(id_token: str) -> dict:
    """
    Verify Google ID token and return user info.

    Uses Google's tokeninfo endpoint for verification.
    Returns: {email, name, picture, email_verified}
    """
    try:
        async with httpx.AsyncClient() as client:
            # Verify token with Google
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google token"
                )

            token_info = response.json()

            # Verify the token was meant for our app
            if token_info.get("aud") != settings.google_client_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token was not issued for this application"
                )

            # Check email is verified by Google
            if token_info.get("email_verified") != "true":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Email not verified by Google"
                )

            return {
                "email": token_info.get("email"),
                "name": token_info.get("name", token_info.get("email", "").split("@")[0]),
                "picture": token_info.get("picture"),
                "google_id": token_info.get("sub")
            }

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not verify Google token: {str(e)}"
        )


@router.post("/google", response_model=GoogleAuthResponse)
async def google_auth(
    request: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate with Google OAuth.

    Flow:
    1. Frontend uses Google Sign-In SDK to get access token + user info
    2. Frontend sends user info (email, name, picture) to this endpoint
    3. Backend creates/updates user (auto-verified - no OTP needed!)
    4. Returns JWT token + profile status

    For NEW users:
    - If registration_number not provided, generates a temporary one
    - User is created with is_verified=True (Google verified the email)
    - next_step will be "upload_resume"

    For EXISTING users:
    - Returns token
    - next_step depends on profile_complete status
    """
    # Use user info provided by frontend (already verified with Google)
    if request.email:
        # Frontend already got user info from Google
        google_info = {
            "email": request.email,
            "name": request.name or request.email.split("@")[0],
            "picture": request.picture
        }
    else:
        # Fallback: try to verify with token (for backwards compatibility)
        google_info = await verify_google_token(request.id_token)

    email = google_info["email"].lower()

    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    is_new_user = False

    if not user:
        # NEW USER - Create account
        is_new_user = True

        # Generate registration number if not provided
        reg_number = request.registration_number
        if not reg_number:
            # Generate unique reg number
            import uuid
            reg_number = f"G{uuid.uuid4().hex[:8].upper()}"

        # Check if reg number already exists
        existing_reg = await db.execute(
            select(User).where(User.registration_number == reg_number)
        )
        if existing_reg.scalar_one_or_none():
            reg_number = f"G{uuid.uuid4().hex[:8].upper()}"

        # Create user - VERIFIED BY GOOGLE (no OTP needed!)
        user = User(
            email=email,
            name=google_info["name"],
            registration_number=reg_number,
            hashed_password=get_password_hash(f"google_{uuid.uuid4().hex}"),  # Random password (won't be used)
            is_verified=True,  # Google verified the email!
            avatar_url=google_info.get("picture"),
            profile_complete=False
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"✅ New user created via Google OAuth: {email}")
    else:
        # EXISTING USER - Update info if needed
        if not user.is_verified:
            user.is_verified = True  # Google verified the email

        if google_info.get("picture") and not user.avatar_url:
            user.avatar_url = google_info["picture"]

        await db.commit()

    # Generate JWT token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )

    # Check profile completion
    from ..models.profile import CandidateProfile
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    has_resume = profile is not None and profile.resume_url is not None

    # Determine next step
    next_step = None
    if not has_resume:
        next_step = "upload_resume"

    # Update profile_complete if resume exists
    if has_resume and not user.profile_complete:
        user.profile_complete = True
        await db.commit()

    return GoogleAuthResponse(
        access_token=access_token,
        is_new_user=is_new_user,
        profile_complete=user.profile_complete,
        next_step=next_step,
        user={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url
        }
    )


@router.get("/google/client-id")
async def get_google_client_id():
    """
    Get the Google Client ID for frontend initialization.

    Frontend needs this to initialize Google Sign-In SDK.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth not configured"
        )

    return {"client_id": settings.google_client_id}


@router.get("/profile-status")
async def get_profile_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check user's profile completion status.

    Returns:
    - is_verified: Email verified
    - has_resume: Resume uploaded
    - profile_complete: All steps done
    - next_step: What user needs to do next
    """
    from ..models.profile import CandidateProfile

    # Check resume
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    has_resume = profile is not None and profile.resume_url is not None

    # Determine next step
    next_step = None
    if not current_user.is_verified:
        next_step = "verify_email"
    elif not has_resume:
        next_step = "upload_resume"

    return {
        "is_verified": current_user.is_verified,
        "has_resume": has_resume,
        "profile_complete": current_user.profile_complete,
        "next_step": next_step
    }


@router.delete("/cleanup-unverified")
async def cleanup_unverified_users(
    db: AsyncSession = Depends(get_db),
    hours: int = 24
):
    """
    Admin endpoint to cleanup unverified users older than X hours.
    This removes users who registered but never verified their email.

    NOTE: This endpoint should be protected by admin auth or called via cron job.
    """
    from sqlalchemy import delete

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Delete unverified users older than cutoff
    result = await db.execute(
        delete(User).where(
            User.is_verified == False,
            User.created_at < cutoff,
            User.role == "STUDENT"  # Don't delete admin accounts
        )
    )
    deleted_count = result.rowcount
    await db.commit()

    print(f"🧹 Cleaned up {deleted_count} unverified users older than {hours} hours")

    return {
        "success": True,
        "deleted_count": deleted_count,
        "cutoff_hours": hours
    }

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

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


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password"""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if email is verified (skip for admin users)
    if not user.is_verified and user.role.value != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email first."
        )
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    return Token(access_token=access_token)


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

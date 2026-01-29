"""
Profile Router - Resume upload, parsing, and profile CRUD operations
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import User, CandidateProfile, Skill, Education, WorkExperience, Project
from ..models import Certification, Publication, Award, UserLanguage
from ..models import SkillCategory, ProficiencyLevel, LanguageProficiency
from ..models import ResumeParsingJob, ResumeParsingStatus
from ..services.auth import get_current_user
from ..services.resume_parser import (
    parse_resume_with_gemini, parse_resume_safe, 
    normalize_skill_name, deduplicate_skills
)
from ..services.vector_search import vector_search_service
from ..schemas.profile import (
    ProfileResponse, ProfileUpdate,
    EducationCreate, WorkExperienceCreate, ProjectCreate,
    CertificationCreate, PublicationCreate, AwardCreate, UserLanguageCreate,
    SkillResponse
)

router = APIRouter(prefix="/api/profile", tags=["Profile"])


# ============================================================================
# Helper Functions
# ============================================================================

async def get_or_create_skill(db: AsyncSession, name: str, category: str = "other") -> Skill:
    """Get existing skill or create new one."""
    normalized = normalize_skill_name(name)
    
    result = await db.execute(
        select(Skill).where(Skill.name == normalized)
    )
    skill = result.scalar_one_or_none()
    
    if not skill:
        # Map category string to enum
        category_map = {
            "language": SkillCategory.LANGUAGE,
            "framework": SkillCategory.FRAMEWORK,
            "database": SkillCategory.DATABASE,
            "cloud": SkillCategory.CLOUD,
            "tool": SkillCategory.TOOL,
            "soft_skill": SkillCategory.SOFT_SKILL,
        }
        skill_category = category_map.get(category, SkillCategory.OTHER)
        
        skill = Skill(
            name=normalized,
            display_name=name,
            category=skill_category
        )
        db.add(skill)
        await db.flush()  # Get the ID
    
    return skill


async def get_profile_with_relations(db: AsyncSession, user_id: int) -> Optional[CandidateProfile]:
    """Get profile with all related data loaded."""
    result = await db.execute(
        select(CandidateProfile)
        .options(
            selectinload(CandidateProfile.education),
            selectinload(CandidateProfile.work_experience),
            selectinload(CandidateProfile.projects),
            selectinload(CandidateProfile.skills),
            selectinload(CandidateProfile.certifications),
            selectinload(CandidateProfile.publications),
            selectinload(CandidateProfile.awards),
            selectinload(CandidateProfile.languages),
        )
        .where(CandidateProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()


# ============================================================================
# Profile Endpoints
# ============================================================================

@router.post("/complete-profile")
async def complete_profile(
    full_name: str,
    knows_data_annotation: str = "no",  # "yes" or "no"
    why_annotation: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Complete initial profile setup - saves all onboarding wizard data.
    Called during onboarding wizard.
    """
    # Update user's name
    current_user.name = full_name.strip()
    
    # Create profile if doesn't exist
    profile = await get_profile_with_relations(db, current_user.id)
    if not profile:
        profile = CandidateProfile(user_id=current_user.id)
        db.add(profile)
        await db.flush()
    
    # Save wizard answers to profile
    profile.has_data_annotation_experience = (knows_data_annotation.lower() == "yes")
    profile.why_annotation = why_annotation.strip() if why_annotation else None
    
    await db.commit()
    
    return {"success": True, "message": "Profile setup complete"}

@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload resume - returns immediately, parses in background.
    
    Scalable for 10K+ candidates:
    - Returns immediately with job_id (or 0 if table doesn't exist)
    - Parsing happens asynchronously using asyncio.create_task
    - Check status via GET /api/profile/resume-status/{job_id}
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # Read file
    pdf_bytes = await file.read()
    
    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 10MB"
        )
    
    # Try to create job record (graceful if table doesn't exist)
    job_id = 0
    job_tracking_enabled = False
    try:
        job = ResumeParsingJob(
            user_id=current_user.id,
            resume_filename=file.filename,
            status=ResumeParsingStatus.PENDING
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id
        job_tracking_enabled = True
        print(f"Created resume parsing job {job_id} for user {current_user.id}")
    except Exception as e:
        # Table might not exist - continue without job tracking
        print(f"Job tracking disabled (table may not exist): {e}")
        await db.rollback()
    
    # Fire and forget - process in background (non-blocking)
    asyncio.create_task(
        process_resume_background(
            job_id=job_id if job_tracking_enabled else None,
            user_id=current_user.id,
            pdf_bytes=pdf_bytes,
            filename=file.filename
        )
    )
    
    return {
        "status": "processing",
        "job_id": job_id,
        "message": "Resume uploaded. Parsing in background - check status in a few seconds."
    }


@router.get("/resume-status/{job_id}")
async def get_resume_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Check the status of a resume parsing job."""
    result = await db.execute(
        select(ResumeParsingJob).where(
            ResumeParsingJob.id == job_id,
            ResumeParsingJob.user_id == current_user.id
        )
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return {
        "job_id": job.id,
        "status": job.status.value,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }


@router.get("/resume-status")
async def get_latest_resume_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the status of the user's most recent resume parsing job.

    Auto-detects stuck jobs (PROCESSING for > 5 minutes) and marks them as failed.
    """
    result = await db.execute(
        select(ResumeParsingJob)
        .where(ResumeParsingJob.user_id == current_user.id)
        .order_by(ResumeParsingJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()

    if not job:
        return {"status": "none", "message": "No resume parsing jobs found"}

    # Auto-detect stuck jobs (PROCESSING for more than 5 minutes)
    if job.status == ResumeParsingStatus.PROCESSING and job.started_at:
        stuck_threshold = datetime.now(timezone.utc) - job.started_at
        if stuck_threshold.total_seconds() > 300:  # 5 minutes
            job.status = ResumeParsingStatus.FAILED
            job.error_message = "Job timed out (stuck in processing). Please retry."
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

    return {
        "job_id": job.id,
        "status": job.status.value,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "can_retry": job.status == ResumeParsingStatus.FAILED
    }


@router.post("/retry-resume")
async def retry_resume_parsing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retry a failed resume parsing job.

    Only works if:
    - User has a failed job
    - Resume file is still available in storage
    """
    # Get the most recent failed job
    result = await db.execute(
        select(ResumeParsingJob)
        .where(
            ResumeParsingJob.user_id == current_user.id,
            ResumeParsingJob.status == ResumeParsingStatus.FAILED
        )
        .order_by(ResumeParsingJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No failed resume job found to retry"
        )

    # Check retry limit
    if job.retry_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum retry attempts (3) reached. Please upload a new resume."
        )

    # Get the resume from storage
    from ..models import CandidateProfile
    profile_result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    if not profile or not profile.resume_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No resume file found. Please upload a new resume."
        )

    # Fetch the resume from storage
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if profile.resume_url.startswith("/uploads/"):
                # Local storage - can't fetch via HTTP in this context
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Resume stored locally. Please upload again."
                )
            response = await client.get(profile.resume_url)
            response.raise_for_status()
            pdf_bytes = response.content
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not fetch resume from storage: {str(e)}"
        )

    # Reset job status and increment retry count
    job.status = ResumeParsingStatus.PENDING
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    job.retry_count += 1
    await db.commit()

    # Fire background task
    asyncio.create_task(
        process_resume_background(
            job_id=job.id,
            user_id=current_user.id,
            pdf_bytes=pdf_bytes,
            filename=job.resume_filename or "resume.pdf"
        )
    )

    return {
        "status": "retrying",
        "job_id": job.id,
        "retry_count": job.retry_count,
        "message": "Resume parsing retry started"
    }


# ============================================================================
# Background Processing Function
# ============================================================================

async def process_resume_background(
    job_id: Optional[int],
    user_id: int,
    pdf_bytes: bytes,
    filename: str
):
    """
    Background task to parse resume and update profile.
    
    This runs in the same event loop as the main app but doesn't block.
    Uses a fresh database session to avoid connection issues.
    
    Works with or without job tracking (job_id can be None).
    """
    from ..database import async_session_maker
    
    async with async_session_maker() as db:
        try:
            job = None
            
            # Try to mark job as processing (if job tracking is enabled)
            if job_id:
                try:
                    result = await db.execute(
                        select(ResumeParsingJob).where(ResumeParsingJob.id == job_id)
                    )
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = ResumeParsingStatus.PROCESSING
                        job.started_at = datetime.now(timezone.utc)
                        await db.commit()
                except Exception as e:
                    print(f"Could not update job status: {e}")
                    job = None
            
            # Parse resume with retries
            parsed, error = await parse_resume_safe(pdf_bytes, max_retries=3)
            
            if error or not parsed:
                error_msg = error or "Parsing returned no data"
                print(f"Resume parsing failed for user {user_id}: {error_msg}")
                
                # Mark job as failed if tracking is enabled
                if job:
                    try:
                        job.status = ResumeParsingStatus.FAILED
                        job.error_message = error_msg
                        job.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                    except Exception:
                        pass
                return
            
            # Upload resume to Supabase storage with retry + local fallback
            resume_url = None
            try:
                from ..services.supabase_upload import upload_bytes_to_supabase
                import uuid
                import os
                import aiofiles

                # Generate unique filename: user_123_uuid_originalname.pdf
                unique_id = str(uuid.uuid4())  # Full UUID for uniqueness
                safe_filename = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
                storage_path = f"resumes/user_{user_id}_{unique_id[:12]}_{safe_filename}"

                # Try Supabase with 3 retries
                upload_success = False
                for attempt in range(3):
                    try:
                        resume_url = await upload_bytes_to_supabase(
                            content=pdf_bytes,
                            bucket="division-docs",
                            file_path=storage_path,
                            content_type="application/pdf"
                        )
                        print(f"Resume uploaded to Supabase (attempt {attempt + 1}): {resume_url}")
                        upload_success = True
                        break
                    except Exception as upload_err:
                        print(f"Supabase upload attempt {attempt + 1} failed: {upload_err}")
                        if attempt < 2:
                            await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

                # Fallback to local storage if Supabase failed
                if not upload_success:
                    print("Supabase failed after 3 attempts, falling back to local storage...")
                    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "resumes")
                    os.makedirs(uploads_dir, exist_ok=True)

                    local_filename = f"user_{user_id}_{unique_id[:12]}_{safe_filename}"
                    local_path = os.path.join(uploads_dir, local_filename)

                    async with aiofiles.open(local_path, 'wb') as f:
                        await f.write(pdf_bytes)

                    resume_url = f"/uploads/resumes/{local_filename}"
                    print(f"Resume saved to local storage: {resume_url}")

            except Exception as e:
                print(f"CRITICAL: Failed to save resume to any storage: {e}")
                # Last resort: save to temp location to prevent data loss
                try:
                    import tempfile
                    temp_path = os.path.join(tempfile.gettempdir(), f"resume_backup_{user_id}_{filename}")
                    with open(temp_path, 'wb') as f:
                        f.write(pdf_bytes)
                    print(f"Emergency backup saved to: {temp_path}")
                except Exception:
                    pass
            
            # Apply parsed data to profile (with resume_url)
            await apply_parsed_to_profile(db, user_id, parsed, filename, resume_url)
            
            # Mark job as complete if tracking is enabled
            if job:
                try:
                    job.status = ResumeParsingStatus.COMPLETED
                    job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                except Exception:
                    pass
            
            print(f"Resume parsing completed for user {user_id}")
            
        except Exception as e:
            print(f"Background resume processing error for user {user_id}: {e}")
            if job_id:
                try:
                    result = await db.execute(
                        select(ResumeParsingJob).where(ResumeParsingJob.id == job_id)
                    )
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = ResumeParsingStatus.FAILED
                        job.error_message = str(e)[:500]
                        job.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                except Exception:
                    pass


async def apply_parsed_to_profile(
    db: AsyncSession,
    user_id: int,
    parsed,
    filename: str,
    resume_url: Optional[str] = None
):
    """Apply parsed resume data to user profile."""
    from ..services.resume_parser import deduplicate_skills
    
    # Get or create profile
    profile = await get_profile_with_relations(db, user_id)
    
    if not profile:
        profile = CandidateProfile(user_id=user_id)
        db.add(profile)
        await db.flush()
        profile = await get_profile_with_relations(db, user_id)
    else:
        # Clear existing related data for re-parse
        profile.education.clear()
        profile.work_experience.clear()
        profile.projects.clear()
        profile.skills.clear()
        profile.certifications.clear()
        profile.publications.clear()
        profile.awards.clear()
    
    # Update profile fields
    profile.resume_filename = filename
    profile.resume_url = resume_url  # Store the Supabase URL
    profile.resume_parsed_at = datetime.now(timezone.utc)
    profile.professional_summary = parsed.professional_summary
    profile.years_of_experience = parsed.years_of_experience
    profile.current_role = parsed.current_role
    profile.current_company = parsed.current_company
    
    # Personal info
    if parsed.personal_info:
        profile.linkedin_url = parsed.personal_info.linkedin_url
        profile.github_url = parsed.personal_info.github_url
        profile.portfolio_url = parsed.personal_info.portfolio_url
        profile.location = parsed.personal_info.location
        
        # Update user's name from resume if available
        if parsed.personal_info.name:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and (not user.name or '@' in user.name or user.name == user.email.split('@')[0]):
                user.name = parsed.personal_info.name
    
    # Coding profiles
    if parsed.coding_profiles:
        profile.leetcode_username = parsed.coding_profiles.leetcode
        profile.codechef_username = parsed.coding_profiles.codechef
        profile.codeforces_username = parsed.coding_profiles.codeforces
        if parsed.coding_profiles.github:
            profile.github_url = f"https://github.com/{parsed.coding_profiles.github}"
    
    # Add education
    for edu in parsed.education:
        profile.education.append(Education(
            school=edu.school,
            degree=edu.degree,
            field_of_study=edu.field_of_study,
            start_year=edu.start_year,
            end_year=edu.end_year,
            gpa=edu.gpa
        ))
    
    # Add work experience
    for exp in parsed.work_experience:
        profile.work_experience.append(WorkExperience(
            company=exp.company,
            role=exp.role,
            city=exp.city,
            country=exp.country,
            start_date=exp.start_date,
            end_date=exp.end_date,
            is_current=exp.is_current,
            description=exp.description
        ))
    
    # Add projects
    for proj in parsed.projects:
        profile.projects.append(Project(
            name=proj.name,
            description=proj.description,
            technologies=proj.technologies,
            start_year=proj.start_year,
            end_year=proj.end_year,
            url=proj.url
        ))
    
    # Add skills (deduplicated)
    deduped_skills = deduplicate_skills(parsed.skills)
    skill_names = []
    for skill_entry in deduped_skills:
        skill = await get_or_create_skill(
            db, 
            skill_entry.name, 
            skill_entry.category or "other"
        )
        if skill not in profile.skills:
            profile.skills.append(skill)
        skill_names.append(skill.name)
    
    # Add certifications
    for cert in parsed.certifications:
        profile.certifications.append(Certification(
            title=cert.title,
            issuer=cert.issuer,
            year=cert.year,
            url=cert.url
        ))
    
    # Add publications
    for pub in parsed.publications:
        profile.publications.append(Publication(
            title=pub.title,
            publisher=pub.publisher,
            year=pub.year,
            url=pub.url
        ))
    
    # Add awards
    for award in parsed.awards:
        profile.awards.append(Award(
            title=award.title,
            issuer=award.issuer,
            year=award.year
        ))
    
    # Add languages from resume
    for lang in parsed.languages:
        prof_map = {
            "native": LanguageProficiency.NATIVE,
            "fluent": LanguageProficiency.FLUENT,
            "intermediate": LanguageProficiency.INTERMEDIATE,
            "basic": LanguageProficiency.BASIC
        }
        proficiency = prof_map.get(lang.proficiency, LanguageProficiency.INTERMEDIATE)
        profile.languages.append(UserLanguage(
            language=lang.language,
            proficiency=proficiency
        ))
    
    await db.flush()
    
    # Index in Pinecone for vector search
    if profile.professional_summary:
        try:
            embedding_id = await vector_search_service.index_profile(
                profile_id=profile.id,
                summary=profile.professional_summary,
                skills=skill_names,
                years_exp=profile.years_of_experience,
                current_role=profile.current_role,
                current_company=profile.current_company
            )
            if embedding_id:
                profile.summary_embedding_id = embedding_id
        except Exception as e:
            print(f"Vector indexing failed (non-critical): {e}")
    
    await db.commit()


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile with all related data."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please upload a resume first."
        )
    
    return profile


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    update_data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update profile fields."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please upload a resume first."
        )
    
    # Update fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(profile, field, value)
    
    # Re-index if summary changed
    if "professional_summary" in update_dict and profile.professional_summary:
        skill_names = [s.name for s in profile.skills]
        await vector_search_service.index_profile(
            profile_id=profile.id,
            summary=profile.professional_summary,
            skills=skill_names,
            years_exp=profile.years_of_experience,
            current_role=profile.current_role,
            current_company=profile.current_company
        )
    
    await db.commit()
    await db.refresh(profile)
    
    return profile


@router.get("/skills", response_model=List[SkillResponse])
async def list_all_skills(
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = None
):
    """Get all available skills for autocomplete."""
    query = select(Skill)
    
    if search:
        query = query.where(Skill.name.ilike(f"%{search}%"))
    
    query = query.order_by(Skill.name).limit(50)
    
    result = await db.execute(query)
    return result.scalars().all()


# ============================================================================
# Resume Download Endpoints (Scalable for 10K+ users)
# ============================================================================

@router.get("/resume/url")
async def get_resume_url(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the URL of the user's uploaded resume.
    
    Returns the resume URL and filename for direct access or embedding.
    Use this for PDF viewers that need a direct URL.
    """
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please upload a resume first."
        )
    
    if not profile.resume_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume uploaded. Please upload a resume first."
        )
    
    return {
        "url": profile.resume_url,
        "filename": profile.resume_filename or "resume.pdf",
        "parsed_at": profile.resume_parsed_at.isoformat() if profile.resume_parsed_at else None
    }


@router.get("/resume/download")
async def download_resume(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download the user's resume as a PDF file.
    
    Scalable for 10K+ users:
    - Uses streaming response (no server memory buffering)
    - Adds proper caching headers for CDN
    - Includes Content-Disposition for proper filename
    
    For local storage: serves file directly
    For Supabase: streams from storage
    """
    import httpx
    from fastapi.responses import StreamingResponse, FileResponse
    import os
    
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please upload a resume first."
        )
    
    if not profile.resume_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume uploaded. Please upload a resume first."
        )
    
    filename = profile.resume_filename or "resume.pdf"
    # Sanitize filename for Content-Disposition header
    safe_filename = filename.replace('"', '\\"').replace('\n', '').replace('\r', '')
    
    # Check if it's a local file or remote URL
    if profile.resume_url.startswith("/uploads/"):
        # Local storage - serve file directly
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        local_path = os.path.join(base_dir, profile.resume_url.lstrip("/"))
        
        if not os.path.exists(local_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume file not found on server. Please upload again."
            )
        
        return FileResponse(
            path=local_path,
            filename=safe_filename,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Cache-Control": "private, max-age=3600"  # Cache for 1 hour
            }
        )
    else:
        # Remote URL (Supabase) - stream the content
        async def stream_from_url():
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("GET", profile.resume_url) as response:
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Failed to fetch resume from storage"
                        )
                    async for chunk in response.aiter_bytes(chunk_size=65536):  # 64KB chunks
                        yield chunk
        
        return StreamingResponse(
            stream_from_url(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Cache-Control": "private, max-age=3600",  # Cache for 1 hour
                "X-Content-Type-Options": "nosniff"
            }
        )


# ============================================================================
# Language (Manual Add/Remove)
# ============================================================================

@router.post("/me/languages", response_model=ProfileResponse)
async def add_language(
    language_data: UserLanguageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a language proficiency to profile."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Map proficiency
    prof_map = {
        "native": LanguageProficiency.NATIVE,
        "fluent": LanguageProficiency.FLUENT,
        "intermediate": LanguageProficiency.INTERMEDIATE,
        "basic": LanguageProficiency.BASIC
    }
    proficiency = prof_map.get(language_data.proficiency, LanguageProficiency.INTERMEDIATE)
    
    profile.languages.append(UserLanguage(
        language=language_data.language,
        proficiency=proficiency
    ))
    
    await db.commit()
    profile = await get_profile_with_relations(db, current_user.id)
    
    return profile


@router.delete("/me/languages/{language_id}")
async def remove_language(
    language_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a language from profile."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Find and remove the language
    for lang in profile.languages:
        if lang.id == language_id:
            profile.languages.remove(lang)
            await db.commit()
            return {"message": "Language removed"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Language not found"
    )

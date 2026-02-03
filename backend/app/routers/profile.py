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
    EducationCreate, EducationUpdate,
    WorkExperienceCreate, WorkExperienceUpdate,
    ProjectCreate, ProjectUpdate,
    CertificationCreate, PublicationCreate, AwardCreate, UserLanguageCreate,
    SkillResponse, SkillAdd,
    EducationResponse, WorkExperienceResponse, ProjectResponse
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
    Upload resume with GUARANTEED file save, then parse in background.

    CRITICAL FLOW (ensures 100% resume save):
    1. Validate file → FAIL FAST if invalid
    2. Upload to storage (Supabase/local) → SYNCHRONOUS, must succeed
    3. Save resume_url to profile → SYNCHRONOUS, must succeed
    4. Create parsing job → THEN fire background parsing

    This ensures: Even if parsing fails/crashes, the resume file is SAVED.
    User can always retry parsing without re-uploading.
    """
    import re
    import uuid
    import os
    import aiofiles

    # ===== STEP 1: VALIDATE FILE =====
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )

    pdf_bytes = await file.read()

    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 10MB"
        )

    # ===== STEP 2: UPLOAD FILE TO STORAGE (SYNCHRONOUS - MUST SUCCEED) =====
    resume_url = None
    unique_id = str(uuid.uuid4())

    # Sanitize filename for storage
    safe_filename = file.filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    safe_filename = re.sub(r'[\[\]\(\)\{\}<>\'\"#%&\+\=\|\^]', '', safe_filename)
    safe_filename = re.sub(r'_+', '_', safe_filename)
    storage_path = f"resumes/user_{current_user.id}_{unique_id[:12]}_{safe_filename}"

    # Try Supabase first, then local fallback
    try:
        from ..services.supabase_upload import upload_bytes_to_supabase

        for attempt in range(3):
            try:
                resume_url = await upload_bytes_to_supabase(
                    content=pdf_bytes,
                    bucket="division-docs",
                    file_path=storage_path,
                    content_type="application/pdf"
                )
                print(f"✅ Resume uploaded to Supabase: {resume_url}")
                break
            except Exception as upload_err:
                print(f"Supabase attempt {attempt + 1}/3 failed: {upload_err}")
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
    except Exception as e:
        print(f"Supabase module error: {e}")

    # Fallback to local storage if Supabase failed
    if not resume_url:
        print("⚠️ Supabase failed, using local storage...")
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "resumes")
        os.makedirs(uploads_dir, exist_ok=True)

        local_filename = f"user_{current_user.id}_{unique_id[:12]}_{safe_filename}"
        local_filename = re.sub(r'[^\w\-_\.]', '', local_filename)
        local_path = os.path.join(uploads_dir, local_filename)

        async with aiofiles.open(local_path, 'wb') as f:
            await f.write(pdf_bytes)

        resume_url = f"/uploads/resumes/{local_filename}"
        print(f"✅ Resume saved to local storage: {resume_url}")

    if not resume_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save resume file. Please try again."
        )

    # ===== STEP 3: SAVE RESUME URL TO PROFILE (SYNCHRONOUS - MUST SUCCEED) =====
    profile = await get_profile_with_relations(db, current_user.id)

    if not profile:
        profile = CandidateProfile(user_id=current_user.id)
        db.add(profile)
        await db.flush()

    # Save file reference IMMEDIATELY
    profile.resume_filename = _safe_truncate(file.filename, 255)
    profile.resume_url = _safe_truncate(resume_url, 500)
    profile.resume_parsed_at = None  # Will be set after parsing completes

    # Mark user's profile as complete (resume requirement fulfilled)
    current_user.profile_complete = True

    await db.commit()
    print(f"✅ Resume URL saved to profile for user {current_user.id}")
    print(f"✅ Profile marked as complete for user {current_user.id}")

    # ===== STEP 4: CREATE PARSING JOB AND FIRE BACKGROUND TASK =====
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
        print(f"Job tracking disabled: {e}")
        await db.rollback()

    # Fire background parsing (resume is ALREADY saved, this can fail safely)
    asyncio.create_task(
        process_resume_background(
            job_id=job_id if job_tracking_enabled else None,
            user_id=current_user.id,
            pdf_bytes=pdf_bytes,
            filename=file.filename,
            resume_url=resume_url  # Pass the already-saved URL
        )
    )

    return {
        "status": "processing",
        "job_id": job_id,
        "resume_saved": True,  # Confirms file is 100% saved
        "resume_url": resume_url,
        "message": "Resume saved successfully. Parsing in background - check status in a few seconds."
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

    # Fetch the resume from storage (supports both local and remote)
    import httpx
    import os
    import aiofiles

    pdf_bytes = None
    resume_url = profile.resume_url

    try:
        if resume_url.startswith("/uploads/"):
            # Local storage - read file directly
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            local_path = os.path.join(base_dir, resume_url.lstrip("/"))

            if not os.path.exists(local_path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Resume file not found. Please upload again."
                )

            async with aiofiles.open(local_path, 'rb') as f:
                pdf_bytes = await f.read()
            print(f"Loaded resume from local storage: {local_path}")
        else:
            # Remote storage (Supabase) - fetch via HTTP
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(resume_url)
                response.raise_for_status()
                pdf_bytes = response.content
            print(f"Loaded resume from remote storage: {resume_url}")

    except HTTPException:
        raise
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

    # Fire background task with resume_url (file is already saved)
    asyncio.create_task(
        process_resume_background(
            job_id=job.id,
            user_id=current_user.id,
            pdf_bytes=pdf_bytes,
            filename=job.resume_filename or "resume.pdf",
            resume_url=resume_url
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
    filename: str,
    resume_url: Optional[str] = None  # Already saved by upload endpoint
):
    """
    Background task to PARSE resume and update profile.

    IMPORTANT: The resume file is ALREADY SAVED before this runs.
    This function only handles AI parsing - if it fails, the file is still safe.

    The user can retry parsing without re-uploading the file.
    """
    from ..database import async_session_maker

    async with async_session_maker() as db:
        try:
            job = None

            # Mark job as processing
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

            # Parse resume with retries + API key rotation
            parsed, error = await parse_resume_safe(pdf_bytes, max_retries=3)

            if error or not parsed:
                error_msg = error or "Parsing returned no data"
                print(f"Resume parsing failed for user {user_id}: {error_msg}")

                # Mark job as failed (but resume file is STILL SAVED!)
                if job:
                    try:
                        job.status = ResumeParsingStatus.FAILED
                        job.error_message = error_msg[:500]
                        job.completed_at = datetime.now(timezone.utc)
                        await db.commit()
                    except Exception:
                        pass
                return

            # Apply parsed data to profile
            # resume_url is already saved, this just adds the parsed fields
            await apply_parsed_to_profile(db, user_id, parsed, filename, resume_url)

            # Mark job as complete
            if job:
                try:
                    job.status = ResumeParsingStatus.COMPLETED
                    job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                except Exception:
                    pass

            print(f"✅ Resume parsing completed for user {user_id}")

        except Exception as e:
            print(f"Background parsing error for user {user_id}: {e}")
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


def _safe_truncate(value: Optional[str], max_len: int) -> Optional[str]:
    """Safely truncate a string to max_len characters."""
    if value is None:
        return None
    return value[:max_len] if len(value) > max_len else value


async def apply_parsed_to_profile(
    db: AsyncSession,
    user_id: int,
    parsed,
    filename: str,
    resume_url: Optional[str] = None
):
    """
    Apply parsed resume data to user profile.

    CRITICAL: This function must be robust - if parsing fails partially,
    we should still save the resume_url so candidates can re-upload.
    """
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

    # Update resume metadata (URL is already saved by upload endpoint, but update if provided)
    if filename:
        profile.resume_filename = _safe_truncate(filename, 255)
    if resume_url:
        profile.resume_url = _safe_truncate(resume_url, 500)
    # Mark parsing as complete NOW (file was already saved earlier)
    profile.resume_parsed_at = datetime.now(timezone.utc)

    # Update profile fields with truncation
    profile.professional_summary = parsed.professional_summary  # Text field, no limit
    profile.years_of_experience = parsed.years_of_experience
    profile.current_role = _safe_truncate(parsed.current_role, 200)
    profile.current_company = _safe_truncate(parsed.current_company, 200)

    # Personal info
    if parsed.personal_info:
        profile.linkedin_url = _safe_truncate(parsed.personal_info.linkedin_url, 500)
        profile.github_url = _safe_truncate(parsed.personal_info.github_url, 500)
        profile.portfolio_url = _safe_truncate(parsed.personal_info.portfolio_url, 500)
        profile.location = _safe_truncate(parsed.personal_info.location, 200)

        # Update user's name from resume if available
        if parsed.personal_info.name:
            try:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user and (not user.name or '@' in user.name or user.name == user.email.split('@')[0]):
                    user.name = _safe_truncate(parsed.personal_info.name, 255)
            except Exception as e:
                print(f"Failed to update user name: {e}")

    # Coding profiles
    if parsed.coding_profiles:
        profile.leetcode_username = _safe_truncate(parsed.coding_profiles.leetcode, 100)
        profile.codechef_username = _safe_truncate(parsed.coding_profiles.codechef, 100)
        profile.codeforces_username = _safe_truncate(parsed.coding_profiles.codeforces, 100)
        if parsed.coding_profiles.github:
            profile.github_url = _safe_truncate(f"https://github.com/{parsed.coding_profiles.github}", 500)

    # COMMIT resume URL first - ensures we don't lose the file reference
    try:
        await db.flush()
    except Exception as e:
        print(f"Failed to save basic profile info: {e}")
        await db.rollback()
        raise

    # Add education with defensive truncation
    # GPA column is now VARCHAR(100) after migration - can store "9.25 (3rd Rank in Class)" etc.
    for edu in parsed.education:
        try:
            profile.education.append(Education(
                school=_safe_truncate(edu.school, 300),
                degree=_safe_truncate(edu.degree, 200),
                field_of_study=_safe_truncate(edu.field_of_study, 200),
                start_year=edu.start_year,
                end_year=edu.end_year,
                gpa=_safe_truncate(edu.gpa, 100)  # VARCHAR(100) after migration
            ))
        except Exception as e:
            print(f"Failed to add education entry: {e}")
            continue  # Skip this entry, continue with others

    # Add work experience with defensive truncation
    for exp in parsed.work_experience:
        try:
            profile.work_experience.append(WorkExperience(
                company=_safe_truncate(exp.company, 300),
                role=_safe_truncate(exp.role, 200),
                city=_safe_truncate(exp.city, 100),
                country=_safe_truncate(exp.country, 100),
                start_date=_safe_truncate(exp.start_date, 20),
                end_date=_safe_truncate(exp.end_date, 20),
                is_current=exp.is_current,
                description=exp.description  # Text field, no limit
            ))
        except Exception as e:
            print(f"Failed to add work experience entry: {e}")
            continue

    # Add projects with defensive truncation
    for proj in parsed.projects:
        try:
            profile.projects.append(Project(
                name=_safe_truncate(proj.name, 300),
                description=proj.description,  # Text field
                technologies=proj.technologies[:20] if proj.technologies else [],  # Limit array size
                start_year=proj.start_year,
                end_year=proj.end_year,
                url=_safe_truncate(proj.url, 500)
            ))
        except Exception as e:
            print(f"Failed to add project entry: {e}")
            continue

    # Add skills (deduplicated)
    skill_names = []
    try:
        deduped_skills = deduplicate_skills(parsed.skills)
        for skill_entry in deduped_skills[:50]:  # Limit to 50 skills
            try:
                skill = await get_or_create_skill(
                    db,
                    _safe_truncate(skill_entry.name, 100),
                    skill_entry.category or "other"
                )
                if skill not in profile.skills:
                    profile.skills.append(skill)
                skill_names.append(skill.name)
            except Exception as e:
                print(f"Failed to add skill {skill_entry.name}: {e}")
                continue
    except Exception as e:
        print(f"Failed to process skills: {e}")

    # Add certifications
    for cert in parsed.certifications[:20]:  # Limit count
        try:
            profile.certifications.append(Certification(
                title=_safe_truncate(cert.title, 300),
                issuer=_safe_truncate(cert.issuer, 200),
                year=cert.year,
                url=_safe_truncate(cert.url, 500)
            ))
        except Exception as e:
            print(f"Failed to add certification: {e}")
            continue

    # Add publications
    for pub in parsed.publications[:20]:
        try:
            profile.publications.append(Publication(
                title=_safe_truncate(pub.title, 500),
                publisher=_safe_truncate(pub.publisher, 300),
                year=pub.year,
                url=_safe_truncate(pub.url, 500)
            ))
        except Exception as e:
            print(f"Failed to add publication: {e}")
            continue

    # Add awards
    for award in parsed.awards[:20]:
        try:
            profile.awards.append(Award(
                title=_safe_truncate(award.title, 300),
                issuer=_safe_truncate(award.issuer, 200),
                year=award.year
            ))
        except Exception as e:
            print(f"Failed to add award: {e}")
            continue

    # Add languages from resume
    for lang in parsed.languages[:10]:
        try:
            prof_map = {
                "native": LanguageProficiency.NATIVE,
                "fluent": LanguageProficiency.FLUENT,
                "intermediate": LanguageProficiency.INTERMEDIATE,
                "basic": LanguageProficiency.BASIC
            }
            proficiency = prof_map.get(lang.proficiency, LanguageProficiency.INTERMEDIATE)
            profile.languages.append(UserLanguage(
                language=_safe_truncate(lang.language, 100),
                proficiency=proficiency
            ))
        except Exception as e:
            print(f"Failed to add language: {e}")
            continue

    # Commit all profile data
    try:
        await db.flush()
    except Exception as e:
        print(f"Failed to flush profile data: {e}")
        # Don't rollback - we already saved the resume_url
        await db.rollback()
        # Re-fetch profile and save just the essential fields
        profile = await get_profile_with_relations(db, user_id)
        if profile:
            profile.resume_filename = _safe_truncate(filename, 255)
            profile.resume_url = _safe_truncate(resume_url, 500)
            profile.resume_parsed_at = datetime.now(timezone.utc)
            await db.commit()
        raise

    # Index in Pinecone for vector search (non-critical)
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
            print(f"Vector indexing skipped (non-critical): {str(e)[:100]}")

    await db.commit()
    print(f"✅ Profile saved for user {user_id}: {len(profile.education)} edu, {len(profile.work_experience)} exp, {len(profile.skills)} skills")


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


# ============================================================================
# Education CRUD
# ============================================================================

@router.post("/me/education", response_model=ProfileResponse)
async def add_education(
    edu_data: EducationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new education entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    profile.education.append(Education(
        school=edu_data.school,
        degree=edu_data.degree,
        field_of_study=edu_data.field_of_study,
        start_year=edu_data.start_year,
        end_year=edu_data.end_year,
        gpa=edu_data.gpa
    ))
    
    await db.commit()
    profile = await get_profile_with_relations(db, current_user.id)
    return profile


@router.put("/me/education/{education_id}", response_model=ProfileResponse)
async def update_education(
    education_id: int,
    edu_data: EducationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an education entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Find the education entry
    education = None
    for edu in profile.education:
        if edu.id == education_id:
            education = edu
            break
    
    if not education:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Education entry not found"
        )
    
    # Update fields that were provided
    update_dict = edu_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(education, field, value)
    
    await db.commit()
    profile = await get_profile_with_relations(db, current_user.id)
    return profile


@router.delete("/me/education/{education_id}")
async def delete_education(
    education_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an education entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    for edu in profile.education:
        if edu.id == education_id:
            profile.education.remove(edu)
            await db.commit()
            return {"message": "Education entry deleted"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Education entry not found"
    )


# ============================================================================
# Work Experience CRUD
# ============================================================================

@router.post("/me/experience", response_model=ProfileResponse)
async def add_experience(
    exp_data: WorkExperienceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new work experience entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    profile.work_experience.append(WorkExperience(
        company=exp_data.company,
        role=exp_data.role,
        city=exp_data.city,
        country=exp_data.country,
        start_date=exp_data.start_date,
        end_date=exp_data.end_date,
        is_current=exp_data.is_current,
        description=exp_data.description
    ))
    
    await db.commit()
    profile = await get_profile_with_relations(db, current_user.id)
    return profile


@router.put("/me/experience/{experience_id}", response_model=ProfileResponse)
async def update_experience(
    experience_id: int,
    exp_data: WorkExperienceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a work experience entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Find the experience entry
    experience = None
    for exp in profile.work_experience:
        if exp.id == experience_id:
            experience = exp
            break
    
    if not experience:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work experience entry not found"
        )
    
    # Update fields that were provided
    update_dict = exp_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(experience, field, value)
    
    await db.commit()
    profile = await get_profile_with_relations(db, current_user.id)
    return profile


@router.delete("/me/experience/{experience_id}")
async def delete_experience(
    experience_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a work experience entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    for exp in profile.work_experience:
        if exp.id == experience_id:
            profile.work_experience.remove(exp)
            await db.commit()
            return {"message": "Work experience entry deleted"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Work experience entry not found"
    )


# ============================================================================
# Project CRUD
# ============================================================================

@router.post("/me/projects", response_model=ProfileResponse)
async def add_project(
    proj_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a new project entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    profile.projects.append(Project(
        name=proj_data.name,
        description=proj_data.description,
        technologies=proj_data.technologies,
        start_year=proj_data.start_year,
        end_year=proj_data.end_year,
        url=proj_data.url
    ))
    
    await db.commit()
    profile = await get_profile_with_relations(db, current_user.id)
    return profile


@router.put("/me/projects/{project_id}", response_model=ProfileResponse)
async def update_project(
    project_id: int,
    proj_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a project entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Find the project
    project = None
    for proj in profile.projects:
        if proj.id == project_id:
            project = proj
            break
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update fields that were provided
    update_dict = proj_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(project, field, value)
    
    await db.commit()
    profile = await get_profile_with_relations(db, current_user.id)
    return profile


@router.delete("/me/projects/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a project entry."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    for proj in profile.projects:
        if proj.id == project_id:
            profile.projects.remove(proj)
            await db.commit()
            return {"message": "Project deleted"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Project not found"
    )


# ============================================================================
# Skills (Add/Remove only - skills are shared entities)
# ============================================================================

@router.post("/me/skills", response_model=ProfileResponse)
async def add_skill(
    skill_data: SkillAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a skill to user's profile."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    # Get or create the skill
    skill = await get_or_create_skill(db, skill_data.name, skill_data.category or "other")
    
    # Check if skill already exists in profile
    if skill in profile.skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skill already added to profile"
        )
    
    profile.skills.append(skill)
    await db.commit()
    profile = await get_profile_with_relations(db, current_user.id)
    return profile


@router.delete("/me/skills/{skill_id}")
async def remove_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a skill from user's profile."""
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    
    for skill in profile.skills:
        if skill.id == skill_id:
            profile.skills.remove(skill)
            await db.commit()
            return {"message": "Skill removed from profile"}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Skill not found in profile"
    )


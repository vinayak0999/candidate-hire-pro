"""
Profile Router - Resume upload, parsing, and profile CRUD operations
"""
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
from ..services.auth import get_current_user
from ..services.resume_parser import parse_resume_with_gemini, normalize_skill_name, deduplicate_skills
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

@router.post("/upload-resume", response_model=ProfileResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload and parse a resume PDF.
    Creates or updates the user's profile with extracted data.
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
    
    # Parse resume with Gemini
    try:
        parsed = await parse_resume_with_gemini(pdf_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse resume: {str(e)}"
        )
    
    # Get or create profile
    profile = await get_profile_with_relations(db, current_user.id)
    
    if not profile:
        profile = CandidateProfile(user_id=current_user.id)
        db.add(profile)
        await db.flush()  # Get the ID
        # Reload with relations to avoid lazy loading issues
        profile = await get_profile_with_relations(db, current_user.id)
    else:
        # Clear existing related data for re-parse
        profile.education.clear()
        profile.work_experience.clear()
        profile.projects.clear()
        profile.skills.clear()
        profile.certifications.clear()
        profile.publications.clear()
        profile.awards.clear()
        # Keep languages as they're manually added
    
    # Update profile fields
    profile.resume_filename = file.filename
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
        
        # Update user's name from resume if available and user's name was auto-generated
        if parsed.personal_info.name:
            # Only update if current name looks auto-generated (email prefix or missing)
            if not current_user.name or '@' in current_user.name or current_user.name == current_user.email.split('@')[0]:
                current_user.name = parsed.personal_info.name
    
    # Coding profiles
    if parsed.coding_profiles:
        profile.leetcode_username = parsed.coding_profiles.leetcode
        profile.codechef_username = parsed.coding_profiles.codechef
        profile.codeforces_username = parsed.coding_profiles.codeforces
        # GitHub might be in coding_profiles or personal_info
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
    
    # Add languages from resume (if any)
    for lang in parsed.languages:
        # Map proficiency
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
    
    await db.commit()
    await db.refresh(profile)
    
    # Reload with relations
    profile = await get_profile_with_relations(db, current_user.id)
    
    return profile


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

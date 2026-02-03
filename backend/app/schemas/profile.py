"""
Profile schemas for resume parsing and candidate profiles
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Profile Response Schemas
# ============================================================================

class EducationResponse(BaseModel):
    id: int
    school: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    gpa: Optional[str] = None

    class Config:
        from_attributes = True


class WorkExperienceResponse(BaseModel):
    id: int
    company: str
    role: str
    city: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    url: Optional[str] = None

    class Config:
        from_attributes = True


class SkillResponse(BaseModel):
    id: int
    name: str
    display_name: str
    category: Optional[str] = None

    class Config:
        from_attributes = True


class CertificationResponse(BaseModel):
    id: int
    title: str
    issuer: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None

    class Config:
        from_attributes = True


class PublicationResponse(BaseModel):
    id: int
    title: str
    publisher: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None

    class Config:
        from_attributes = True


class AwardResponse(BaseModel):
    id: int
    title: str
    issuer: Optional[str] = None
    year: Optional[int] = None

    class Config:
        from_attributes = True


class UserLanguageResponse(BaseModel):
    id: int
    language: str
    proficiency: Optional[str] = None

    class Config:
        from_attributes = True


class ProfileResponse(BaseModel):
    """Full profile response"""
    id: int
    user_id: int
    resume_url: Optional[str] = None
    resume_filename: Optional[str] = None
    resume_parsed_at: Optional[datetime] = None
    
    professional_summary: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    location: Optional[str] = None
    
    years_of_experience: Optional[float] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    
    leetcode_username: Optional[str] = None
    codechef_username: Optional[str] = None
    codeforces_username: Optional[str] = None
    
    # Onboarding wizard data
    has_data_annotation_experience: Optional[bool] = None
    why_annotation: Optional[str] = None
    
    education: List[EducationResponse] = Field(default_factory=list)
    work_experience: List[WorkExperienceResponse] = Field(default_factory=list)
    projects: List[ProjectResponse] = Field(default_factory=list)
    skills: List[SkillResponse] = Field(default_factory=list)
    certifications: List[CertificationResponse] = Field(default_factory=list)
    publications: List[PublicationResponse] = Field(default_factory=list)
    awards: List[AwardResponse] = Field(default_factory=list)
    languages: List[UserLanguageResponse] = Field(default_factory=list)
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# Profile Update Schemas
# ============================================================================

class EducationCreate(BaseModel):
    school: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    gpa: Optional[str] = None


class WorkExperienceCreate(BaseModel):
    company: str
    role: str
    city: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    url: Optional[str] = None


class CertificationCreate(BaseModel):
    title: str
    issuer: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None


class PublicationCreate(BaseModel):
    title: str
    publisher: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None


class AwardCreate(BaseModel):
    title: str
    issuer: Optional[str] = None
    year: Optional[int] = None


class UserLanguageCreate(BaseModel):
    language: str
    proficiency: Optional[str] = "intermediate"


class EducationUpdate(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    gpa: Optional[str] = None


class WorkExperienceUpdate(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    url: Optional[str] = None


class SkillAdd(BaseModel):
    name: str
    category: Optional[str] = "other"


class ProfileUpdate(BaseModel):
    """Update profile fields"""
    professional_summary: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    location: Optional[str] = None
    years_of_experience: Optional[float] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    leetcode_username: Optional[str] = None
    codechef_username: Optional[str] = None
    codeforces_username: Optional[str] = None


# ============================================================================
# HR Search Schemas
# ============================================================================

class SearchQuery(BaseModel):
    query: str
    skill_filters: Optional[List[str]] = None
    min_experience: Optional[float] = None
    top_k: int = 20


class CandidateSearchResult(BaseModel):
    profile_id: int
    score: float
    name: Optional[str] = None
    email: Optional[str] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    years_exp: Optional[float] = None
    skills: List[str] = Field(default_factory=list)
    professional_summary: Optional[str] = None

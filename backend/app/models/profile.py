"""
Profile models for resume parsing and candidate profiles
"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float,
    ForeignKey, Table, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import enum


class SkillCategory(str, enum.Enum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    DATABASE = "database"
    CLOUD = "cloud"
    TOOL = "tool"
    SOFT_SKILL = "soft_skill"
    OTHER = "other"


class ProficiencyLevel(str, enum.Enum):
    EXPERT = "expert"
    INTERMEDIATE = "intermediate"
    BEGINNER = "beginner"


class LanguageProficiency(str, enum.Enum):
    NATIVE = "native"
    FLUENT = "fluent"
    INTERMEDIATE = "intermediate"
    BASIC = "basic"


# Junction table for Profile <-> Skill many-to-many
profile_skills = Table(
    'profile_skills',
    Base.metadata,
    Column('profile_id', Integer, ForeignKey('candidate_profiles.id', ondelete='CASCADE'), primary_key=True),
    Column('skill_id', Integer, ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True),
    Column('proficiency', SQLEnum(ProficiencyLevel), default=ProficiencyLevel.INTERMEDIATE),
    Column('years_used', Float, nullable=True)
)


class CandidateProfile(Base):
    """Main profile linked to User, populated from resume parsing"""
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    
    # Resume info
    resume_url = Column(String(500), nullable=True)
    resume_filename = Column(String(255), nullable=True)
    resume_parsed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Professional summary (elaborate, 200-400 words for vector search)
    professional_summary = Column(Text, nullable=True)
    summary_embedding_id = Column(String(100), nullable=True)  # Pinecone vector ID
    
    # Contact & Links
    linkedin_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    portfolio_url = Column(String(500), nullable=True)
    location = Column(String(200), nullable=True)
    
    # Extracted metadata for filtering
    years_of_experience = Column(Float, nullable=True)
    current_role = Column(String(200), nullable=True)
    current_company = Column(String(200), nullable=True)
    
    # Coding profiles
    leetcode_username = Column(String(100), nullable=True)
    codechef_username = Column(String(100), nullable=True)
    codeforces_username = Column(String(100), nullable=True)
    
    # Onboarding wizard data
    has_data_annotation_experience = Column(Boolean, nullable=True)
    why_annotation = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="profile")
    education = relationship("Education", back_populates="profile", cascade="all, delete-orphan")
    work_experience = relationship("WorkExperience", back_populates="profile", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="profile", cascade="all, delete-orphan")
    skills = relationship("Skill", secondary=profile_skills, back_populates="profiles")
    certifications = relationship("Certification", back_populates="profile", cascade="all, delete-orphan")
    publications = relationship("Publication", back_populates="profile", cascade="all, delete-orphan")
    awards = relationship("Award", back_populates="profile", cascade="all, delete-orphan")
    languages = relationship("UserLanguage", back_populates="profile", cascade="all, delete-orphan")


class Skill(Base):
    """Normalized skill tags for searching"""
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # lowercase, normalized
    display_name = Column(String(100), nullable=False)  # Original casing
    category = Column(SQLEnum(SkillCategory), default=SkillCategory.OTHER)
    aliases = Column(JSON, default=list)  # ["JS", "Javascript"] → "JavaScript"
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    profiles = relationship("CandidateProfile", secondary=profile_skills, back_populates="skills")


class Education(Base):
    """Education entries from resume"""
    __tablename__ = "education"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False)
    
    school = Column(String(300), nullable=False)
    degree = Column(String(200), nullable=True)
    field_of_study = Column(String(200), nullable=True)
    start_year = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    gpa = Column(String(100), nullable=True)  # Increased from 20 - handles "9.25 (3rd Rank in Class)" etc
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    profile = relationship("CandidateProfile", back_populates="education")


class WorkExperience(Base):
    """Work experience entries from resume"""
    __tablename__ = "work_experience"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False)
    
    company = Column(String(300), nullable=False)
    role = Column(String(200), nullable=False)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    start_date = Column(String(20), nullable=True)  # "YYYY-MM" format
    end_date = Column(String(20), nullable=True)  # "YYYY-MM" or null for current
    is_current = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    profile = relationship("CandidateProfile", back_populates="work_experience")


class Project(Base):
    """Project entries from resume"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False)
    
    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    technologies = Column(JSON, default=list)  # List of tech used
    start_year = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    url = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    profile = relationship("CandidateProfile", back_populates="projects")


class Certification(Base):
    """Professional certifications"""
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False)
    
    title = Column(String(300), nullable=False)
    issuer = Column(String(200), nullable=True)
    year = Column(Integer, nullable=True)
    url = Column(String(500), nullable=True)
    credential_id = Column(String(200), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    profile = relationship("CandidateProfile", back_populates="certifications")


class Publication(Base):
    """Research publications and articles"""
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False)
    
    title = Column(String(500), nullable=False)
    publisher = Column(String(300), nullable=True)
    year = Column(Integer, nullable=True)
    url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    profile = relationship("CandidateProfile", back_populates="publications")


class Award(Base):
    """Awards and honors"""
    __tablename__ = "awards"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False)
    
    title = Column(String(300), nullable=False)
    issuer = Column(String(200), nullable=True)
    year = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    profile = relationship("CandidateProfile", back_populates="awards")


class UserLanguage(Base):
    """Language proficiency (manually added)"""
    __tablename__ = "user_languages"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey('candidate_profiles.id', ondelete='CASCADE'), nullable=False)
    
    language = Column(String(100), nullable=False)
    proficiency = Column(SQLEnum(LanguageProficiency), default=LanguageProficiency.INTERMEDIATE)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    profile = relationship("CandidateProfile", back_populates="languages")

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum as SQLEnum, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import enum


class JobStatus(str, enum.Enum):
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    SELECTED = "selected"


class OfferType(str, enum.Enum):
    DREAM_CORE = "dream_core"
    REGULAR = "regular"
    SUPER_DREAM = "super_dream"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    company_logo = Column(String(500), nullable=True)
    role = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    ctc = Column(Float, nullable=True)  # in LPA
    job_type = Column(String(50), default="Full Time")
    description = Column(String(5000), nullable=True)  # Job description
    offer_type = Column(SQLEnum(OfferType), default=OfferType.REGULAR)
    round_date = Column(DateTime(timezone=True), nullable=True)
    
    # Link to assessment
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=True)
    test = relationship("app.models.test.Test")
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.APPLIED)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())

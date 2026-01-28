"""
Resume Parsing Job Model - Tracks background resume processing status.
"""
from enum import Enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from ..database import Base


class ResumeParsingStatus(str, Enum):
    """Status of a resume parsing job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ResumeParsingJob(Base):
    """
    Tracks resume parsing jobs for background processing.
    Allows users to check status without blocking.
    """
    __tablename__ = "resume_parsing_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # File info
    resume_filename = Column(String(255), nullable=False)
    
    # Status tracking
    status = Column(
        SQLEnum(ResumeParsingStatus), 
        default=ResumeParsingStatus.PENDING,
        nullable=False
    )
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

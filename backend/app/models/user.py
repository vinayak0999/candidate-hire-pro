from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
import enum


class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    registration_number = Column(String(50), unique=True, nullable=False)
    degree = Column(String(100), nullable=True)
    branch = Column(String(200), nullable=True)
    batch = Column(String(10), nullable=True)
    college = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    role = Column(SQLEnum(UserRole), default=UserRole.STUDENT)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Email verification
    is_verified = Column(Boolean, default=False)
    verification_otp = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Password reset
    reset_token = Column(String(64), nullable=True)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Stats
    neo_pat_score = Column(Integer, default=0)
    solved_easy = Column(Integer, default=0)
    solved_medium = Column(Integer, default=0)
    solved_hard = Column(Integer, default=0)
    badges_count = Column(Integer, default=0)
    super_badges_count = Column(Integer, default=0)
    
    # Relationships
    profile = relationship("CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = relationship("UserNotification", back_populates="user", cascade="all, delete-orphan")
    created_notifications = relationship("Notification", back_populates="creator")

"""
Notification Models - Announcements and User Notification Status
"""
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from ..database import Base


class NotificationType(str, Enum):
    ANNOUNCEMENT = "ANNOUNCEMENT"
    INFO = "INFO"
    ALERT = "ALERT"
    SYSTEM = "SYSTEM"


class TargetAudience(str, Enum):
    ALL = "ALL"
    BATCH = "BATCH"
    BRANCH = "BRANCH"


class Notification(Base):
    """
    Notification/Announcement model.
    Admins create these to send messages to candidates.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(SQLEnum(NotificationType), default=NotificationType.ANNOUNCEMENT)
    target_audience = Column(SQLEnum(TargetAudience), default=TargetAudience.ALL)
    target_value = Column(String(100), nullable=True)  # e.g., "2025" for batch, "CSE" for branch
    
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    creator = relationship("User", back_populates="created_notifications")
    user_notifications = relationship("UserNotification", back_populates="notification", cascade="all, delete-orphan")


class UserNotification(Base):
    """
    Tracks read/unread status for each user-notification pair.
    """
    __tablename__ = "user_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_id = Column(Integer, ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="notifications")
    notification = relationship("Notification", back_populates="user_notifications")

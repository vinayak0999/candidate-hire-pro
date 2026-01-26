"""
Notification Schemas - Request/Response models for notifications API
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    """Schema for creating a new notification/announcement"""
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)
    notification_type: str = Field(default="announcement")
    target_audience: str = Field(default="all")
    target_value: Optional[str] = None
    expires_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    """Schema for notification response"""
    id: int
    title: str
    message: str
    notification_type: str
    target_audience: str
    target_value: Optional[str]
    created_by: int
    creator_name: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    is_read: bool = False
    read_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NotificationList(BaseModel):
    """Paginated list of notifications"""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Simple unread count response"""
    unread_count: int


class MarkReadRequest(BaseModel):
    """Request to mark notifications as read"""
    notification_ids: Optional[List[int]] = None  # None = mark all

"""
Notification Router - Admin announcements and candidate notifications
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import User, UserRole, Notification, UserNotification, NotificationType, TargetAudience
from ..models.message import Message
from ..services.auth import get_current_user
from ..schemas.notification import (
    NotificationCreate, NotificationResponse, NotificationList, UnreadCountResponse
)

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# ============================================================================
# Helper Functions
# ============================================================================

async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verify user is admin"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def create_user_notification_if_needed(
    db: AsyncSession,
    notification: Notification,
    user: User
) -> Optional[UserNotification]:
    """Create UserNotification record if user matches target audience"""
    # Check if notification applies to this user
    if notification.target_audience == TargetAudience.ALL:
        pass  # Applies to all
    elif notification.target_audience == TargetAudience.BATCH:
        if user.batch != notification.target_value:
            return None
    elif notification.target_audience == TargetAudience.BRANCH:
        if user.branch != notification.target_value:
            return None
    
    # Check if already exists
    result = await db.execute(
        select(UserNotification).where(
            and_(
                UserNotification.user_id == user.id,
                UserNotification.notification_id == notification.id
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    
    # Create new
    user_notif = UserNotification(
        user_id=user.id,
        notification_id=notification.id,
        is_read=False
    )
    db.add(user_notif)
    return user_notif


# ============================================================================
# Admin Endpoints
# ============================================================================

@router.post("/admin/create", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Create a new announcement/notification (Admin only)"""
    notification = Notification(
        title=notification_data.title,
        message=notification_data.message,
        notification_type=NotificationType(notification_data.notification_type),
        target_audience=TargetAudience(notification_data.target_audience),
        target_value=notification_data.target_value,
        expires_at=notification_data.expires_at,
        created_by=admin.id,
        is_active=True
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    
    return NotificationResponse(
        id=notification.id,
        title=notification.title,
        message=notification.message,
        notification_type=notification.notification_type.value,
        target_audience=notification.target_audience.value,
        target_value=notification.target_value,
        created_by=notification.created_by,
        creator_name=admin.name,
        created_at=notification.created_at,
        expires_at=notification.expires_at,
        is_active=notification.is_active,
        is_read=False
    )


@router.get("/admin/list", response_model=List[NotificationResponse])
async def list_all_notifications(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
    skip: int = 0,
    limit: int = 50
):
    """List all notifications (Admin only)"""
    result = await db.execute(
        select(Notification)
        .options(selectinload(Notification.creator))
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    notifications = result.scalars().all()
    
    return [
        NotificationResponse(
            id=n.id,
            title=n.title,
            message=n.message,
            notification_type=n.notification_type.value,
            target_audience=n.target_audience.value,
            target_value=n.target_value,
            created_by=n.created_by,
            creator_name=n.creator.name if n.creator else None,
            created_at=n.created_at,
            expires_at=n.expires_at,
            is_active=n.is_active,
            is_read=False
        )
        for n in notifications
    ]


@router.delete("/admin/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Delete a notification (Admin only)"""
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    await db.delete(notification)
    await db.commit()
    
    return {"message": "Notification deleted successfully"}


@router.put("/admin/{notification_id}/toggle")
async def toggle_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user)
):
    """Toggle notification active status (Admin only)"""
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    notification.is_active = not notification.is_active
    await db.commit()
    
    return {"message": f"Notification {'activated' if notification.is_active else 'deactivated'}"}


# ============================================================================
# Candidate Endpoints
# ============================================================================

@router.get("/me", response_model=NotificationList)
async def get_my_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 20
):
    """Get current user's notifications"""
    now = datetime.now(timezone.utc)
    
    # Debug: Print user info
    print(f"[Notification Debug] User: {current_user.email}, Batch: {current_user.batch}, Branch: {current_user.branch}")
    
    # First, let's see ALL notifications in the DB (for debug)
    all_notifs_result = await db.execute(select(Notification))
    all_notifs = all_notifs_result.scalars().all()
    print(f"[Notification Debug] Total notifications in DB: {len(all_notifs)}")
    for n in all_notifs:
        print(f"  - ID:{n.id}, Title:{n.title}, Audience:{n.target_audience}, Active:{n.is_active}")
    
    # Get active notifications for this user
    query = select(Notification).where(
        and_(
            Notification.is_active == True,
            or_(
                Notification.expires_at == None,
                Notification.expires_at > now
            ),
            or_(
                Notification.target_audience == TargetAudience.ALL,
                and_(
                    Notification.target_audience == TargetAudience.BATCH,
                    Notification.target_value == current_user.batch
                ),
                and_(
                    Notification.target_audience == TargetAudience.BRANCH,
                    Notification.target_value == current_user.branch
                )
            )
        )
    ).order_by(Notification.created_at.desc())
    
    result = await db.execute(query)
    all_notifications = result.scalars().all()
    print(f"[Notification Debug] Matched notifications: {len(all_notifications)}")
    
    # Ensure UserNotification records exist and get read status
    notifications_with_status = []
    for notif in all_notifications:
        user_notif = await create_user_notification_if_needed(db, notif, current_user)
        if user_notif:
            notifications_with_status.append((notif, user_notif))
    
    await db.commit()
    
    # Filter if unread_only
    if unread_only:
        notifications_with_status = [(n, un) for n, un in notifications_with_status if not un.is_read]
    
    # Calculate counts
    total = len(notifications_with_status)
    unread_count = sum(1 for _, un in notifications_with_status if not un.is_read)
    
    # Paginate
    paginated = notifications_with_status[skip:skip + limit]
    
    # Get creator names
    creator_ids = list(set(n.created_by for n, _ in paginated))
    creators = {}
    if creator_ids:
        result = await db.execute(
            select(User).where(User.id.in_(creator_ids))
        )
        for u in result.scalars().all():
            creators[u.id] = u.name
    
    return NotificationList(
        notifications=[
            NotificationResponse(
                id=n.id,
                title=n.title,
                message=n.message,
                notification_type=n.notification_type.value,
                target_audience=n.target_audience.value,
                target_value=n.target_value,
                created_by=n.created_by,
                creator_name=creators.get(n.created_by),
                created_at=n.created_at,
                expires_at=n.expires_at,
                is_active=n.is_active,
                is_read=un.is_read,
                read_at=un.read_at
            )
            for n, un in paginated
        ],
        total=total,
        unread_count=unread_count
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get count of unread notifications"""
    now = datetime.now(timezone.utc)
    
    # Get notifications for this user
    query = select(Notification).where(
        and_(
            Notification.is_active == True,
            or_(
                Notification.expires_at == None,
                Notification.expires_at > now
            ),
            or_(
                Notification.target_audience == TargetAudience.ALL,
                and_(
                    Notification.target_audience == TargetAudience.BATCH,
                    Notification.target_value == current_user.batch
                ),
                and_(
                    Notification.target_audience == TargetAudience.BRANCH,
                    Notification.target_value == current_user.branch
                )
            )
        )
    )
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    # Count unread
    unread_count = 0
    for notif in notifications:
        # Check if user has read this
        result = await db.execute(
            select(UserNotification).where(
                and_(
                    UserNotification.user_id == current_user.id,
                    UserNotification.notification_id == notif.id
                )
            )
        )
        user_notif = result.scalar_one_or_none()
        if not user_notif or not user_notif.is_read:
            unread_count += 1
    
    return UnreadCountResponse(unread_count=unread_count)


@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a notification as read"""
    result = await db.execute(
        select(UserNotification).where(
            and_(
                UserNotification.user_id == current_user.id,
                UserNotification.notification_id == notification_id
            )
        )
    )
    user_notif = result.scalar_one_or_none()
    
    if not user_notif:
        # Create it
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        user_notif = UserNotification(
            user_id=current_user.id,
            notification_id=notification_id,
            is_read=True,
            read_at=datetime.now(timezone.utc)
        )
        db.add(user_notif)
    else:
        user_notif.is_read = True
        user_notif.read_at = datetime.now(timezone.utc)
    
    await db.commit()
    return {"message": "Marked as read"}


@router.put("/read-all")
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark all notifications as read"""
    now = datetime.now(timezone.utc)
    
    # Get all unread notifications for this user
    query = select(Notification).where(
        and_(
            Notification.is_active == True,
            or_(
                Notification.expires_at == None,
                Notification.expires_at > now
            ),
            or_(
                Notification.target_audience == TargetAudience.ALL,
                and_(
                    Notification.target_audience == TargetAudience.BATCH,
                    Notification.target_value == current_user.batch
                ),
                and_(
                    Notification.target_audience == TargetAudience.BRANCH,
                    Notification.target_value == current_user.branch
                )
            )
        )
    )
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    marked_count = 0
    for notif in notifications:
        result = await db.execute(
            select(UserNotification).where(
                and_(
                    UserNotification.user_id == current_user.id,
                    UserNotification.notification_id == notif.id
                )
            )
        )
        user_notif = result.scalar_one_or_none()
        
        if not user_notif:
            user_notif = UserNotification(
                user_id=current_user.id,
                notification_id=notif.id,
                is_read=True,
                read_at=now
            )
            db.add(user_notif)
            marked_count += 1
        elif not user_notif.is_read:
            user_notif.is_read = True
            user_notif.read_at = now
            marked_count += 1
    
    await db.commit()
    return {"message": f"Marked {marked_count} notifications as read"}


# ============================================================================
# Candidate Messages Endpoints (Personal admin-to-candidate messages)
# ============================================================================

@router.get("/messages/me")
async def get_my_messages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 20
):
    """Get current user's personal messages from admin"""
    query = select(Message).where(Message.recipient_id == current_user.id)
    
    if unread_only:
        query = query.where(Message.is_read == False)
    
    query = query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    # Get total and unread counts
    count_result = await db.execute(
        select(func.count()).where(Message.recipient_id == current_user.id)
    )
    total = count_result.scalar() or 0
    
    unread_result = await db.execute(
        select(func.count()).where(
            and_(
                Message.recipient_id == current_user.id,
                Message.is_read == False
            )
        )
    )
    unread_count = unread_result.scalar() or 0
    
    return {
        "messages": [
            {
                "id": m.id,
                "subject": m.subject,
                "content": m.content,
                "reason": m.reason,
                "sender_name": m.sender.name if m.sender else "Admin",
                "is_read": m.is_read,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ],
        "total": total,
        "unread_count": unread_count
    }


@router.get("/messages/unread-count")
async def get_messages_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get count of unread personal messages"""
    result = await db.execute(
        select(func.count()).where(
            and_(
                Message.recipient_id == current_user.id,
                Message.is_read == False
            )
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}


@router.put("/messages/{message_id}/read")
async def mark_message_as_read(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a personal message as read"""
    result = await db.execute(
        select(Message).where(
            and_(
                Message.id == message_id,
                Message.recipient_id == current_user.id
            )
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )
    
    message.is_read = True
    await db.commit()
    return {"message": "Marked as read"}


@router.put("/messages/read-all")
async def mark_all_messages_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark all personal messages as read"""
    result = await db.execute(
        select(Message).where(
            and_(
                Message.recipient_id == current_user.id,
                Message.is_read == False
            )
        )
    )
    messages = result.scalars().all()
    
    for m in messages:
        m.is_read = True
    
    await db.commit()
    return {"message": f"Marked {len(messages)} messages as read"}


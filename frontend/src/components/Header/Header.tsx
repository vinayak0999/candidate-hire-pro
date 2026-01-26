import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { notificationsApi, messagesApi } from '../../services/api';
import type { User } from '../../types';
import './Header.css';

interface Notification {
    id: number;
    title: string;
    message: string;
    notification_type: string;
    created_at: string;
    is_read: boolean;
}

interface PersonalMessage {
    id: number;
    subject: string;
    content: string;
    reason: string | null;
    sender_name: string;
    is_read: boolean;
    created_at: string;
}

// Combined item for display
interface NotificationItem {
    id: number;
    title: string;
    message: string;
    type: 'notification' | 'message';
    icon: string;
    created_at: string;
    is_read: boolean;
}

interface HeaderProps {
    user: User | null;
    onLogout: () => void;
}

export default function Header({ user, onLogout }: HeaderProps) {
    const [showDropdown, setShowDropdown] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);
    const [items, setItems] = useState<NotificationItem[]>([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const notifRef = useRef<HTMLDivElement>(null);

    // Fetch unread count on mount and periodically
    useEffect(() => {
        fetchUnreadCount();
        const interval = setInterval(fetchUnreadCount, 60000); // Every minute
        return () => clearInterval(interval);
    }, []);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
                setShowNotifications(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const fetchUnreadCount = async () => {
        try {
            // Fetch both notification and message counts
            const [notifData, msgData] = await Promise.all([
                notificationsApi.getUnreadCount(),
                messagesApi.getUnreadCount().catch(() => ({ unread_count: 0 }))
            ]);
            setUnreadCount(notifData.unread_count + msgData.unread_count);
        } catch (err) {
            console.error('Failed to fetch unread count:', err);
        }
    };

    const fetchItems = async () => {
        try {
            // Fetch both notifications and personal messages
            const [notifData, msgData] = await Promise.all([
                notificationsApi.getMyNotifications(false, 0, 5),
                messagesApi.getMyMessages(false, 0, 5).catch(() => ({ messages: [], unread_count: 0 }))
            ]);

            // Convert notifications to combined format
            const notificationItems: NotificationItem[] = (notifData.notifications || []).map((n: Notification) => ({
                id: n.id,
                title: n.title,
                message: n.message,
                type: 'notification' as const,
                icon: n.notification_type?.toUpperCase() === 'ALERT' ? '⚠️' :
                    n.notification_type?.toUpperCase() === 'INFO' ? 'ℹ️' : '📢',
                created_at: n.created_at,
                is_read: n.is_read
            }));

            // Convert messages to combined format
            const messageItems: NotificationItem[] = (msgData.messages || []).map((m: PersonalMessage) => ({
                id: m.id,
                title: m.subject,
                message: m.content,
                type: 'message' as const,
                icon: '✉️',
                created_at: m.created_at,
                is_read: m.is_read
            }));

            // Combine and sort by date (newest first)
            const combined = [...notificationItems, ...messageItems].sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            ).slice(0, 5);

            setItems(combined);
            setUnreadCount(notifData.unread_count + (msgData.unread_count || 0));
        } catch (err) {
            console.error('Failed to fetch notifications:', err);
        }
    };

    const handleItemClick = async (item: NotificationItem) => {
        if (!item.is_read) {
            try {
                if (item.type === 'notification') {
                    await notificationsApi.markAsRead(item.id);
                } else {
                    await messagesApi.markAsRead(item.id);
                }
                setItems(prev =>
                    prev.map(i => (i.id === item.id && i.type === item.type) ? { ...i, is_read: true } : i)
                );
                setUnreadCount(prev => Math.max(0, prev - 1));
            } catch (err) {
                console.error('Failed to mark as read:', err);
            }
        }
    };

    const handleMarkAllRead = async () => {
        try {
            await Promise.all([
                notificationsApi.markAllAsRead(),
                messagesApi.markAllAsRead().catch(() => { })
            ]);
            setItems(prev => prev.map(i => ({ ...i, is_read: true })));
            setUnreadCount(0);
        } catch (err) {
            console.error('Failed to mark all as read:', err);
        }
    };

    const toggleNotifications = () => {
        if (!showNotifications) {
            fetchItems();
        }
        setShowNotifications(!showNotifications);
        setShowDropdown(false);
    };

    const handleLogout = () => {
        setShowDropdown(false);
        onLogout();
    };

    const formatTime = (dateStr: string) => {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    };

    return (
        <header className="header">
            <div className="header-search">
                <div className="search-wrapper">
                    <svg className="search-icon" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
                    </svg>
                    <input type="text" className="search-input" placeholder="Search" />
                </div>
            </div>

            <div className="header-actions">
                {/* Notifications Bell */}
                <div className="notification-wrapper" ref={notifRef}>
                    <button
                        className="header-icon-btn notification-btn"
                        title="Notifications & Messages"
                        onClick={toggleNotifications}
                    >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" />
                        </svg>
                        {unreadCount > 0 && (
                            <span className="notification-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>
                        )}
                    </button>

                    {showNotifications && (
                        <div className="notification-dropdown">
                            <div className="notification-header">
                                <h4>Notifications</h4>
                                {unreadCount > 0 && (
                                    <button className="mark-all-read" onClick={handleMarkAllRead}>
                                        Mark all read
                                    </button>
                                )}
                            </div>
                            <div className="notification-list">
                                {items.length === 0 ? (
                                    <div className="notification-empty">
                                        <span className="empty-icon">🔔</span>
                                        <p>No notifications yet</p>
                                    </div>
                                ) : (
                                    items.map(item => (
                                        <div
                                            key={`${item.type}-${item.id}`}
                                            className={`notification-item ${!item.is_read ? 'unread' : ''}`}
                                            onClick={() => handleItemClick(item)}
                                        >
                                            <div className="notification-icon">
                                                {item.icon}
                                            </div>
                                            <div className="notification-content">
                                                <h5>{item.title}</h5>
                                                <p>{item.message.length > 80 ? item.message.slice(0, 80) + '...' : item.message}</p>
                                                <span className="notification-time">
                                                    {item.type === 'message' && <span className="msg-badge">Personal</span>}
                                                    {formatTime(item.created_at)}
                                                </span>
                                            </div>
                                            {!item.is_read && <span className="unread-dot"></span>}
                                        </div>
                                    ))
                                )}
                            </div>
                            <Link
                                to="/notifications"
                                className="notification-footer"
                                onClick={() => setShowNotifications(false)}
                            >
                                View all notifications
                            </Link>
                        </div>
                    )}
                </div>

                <div className="profile-dropdown">
                    <div
                        className="header-profile"
                        onClick={() => { setShowDropdown(!showDropdown); setShowNotifications(false); }}
                    >
                        <img
                            src={user?.avatar_url || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(user?.name || 'User') + '&background=4361EE&color=fff'}
                            alt="Profile"
                            className="profile-avatar"
                        />
                        <span className="profile-name">{user?.name || 'User'}</span>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M7 10l5 5 5-5z" />
                        </svg>
                    </div>

                    {showDropdown && (
                        <div className="dropdown-menu">
                            <Link to="/profile" className="dropdown-item" onClick={() => setShowDropdown(false)}>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                                </svg>
                                Profile
                            </Link>
                            <button className="dropdown-item danger" onClick={handleLogout}>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" />
                                </svg>
                                Logout
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </header>
    );
}

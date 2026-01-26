import { useState, useEffect } from 'react';
import { notificationsApi, messagesApi } from '../services/api';
import './Notifications.css';

interface NotificationItem {
    id: number;
    title: string;
    message: string;
    type: 'notification' | 'message';
    notification_type?: string;
    sender_name?: string;
    reason?: string;
    created_at: string;
    is_read: boolean;
}

export default function Notifications() {
    const [items, setItems] = useState<NotificationItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<'all' | 'unread'>('all');
    const [tab, setTab] = useState<'all' | 'announcements' | 'messages'>('all');

    useEffect(() => {
        fetchItems();
    }, [filter, tab]);

    const fetchItems = async () => {
        try {
            setLoading(true);
            const unreadOnly = filter === 'unread';

            let notifications: NotificationItem[] = [];
            let messages: NotificationItem[] = [];

            // Fetch based on active tab
            if (tab === 'all' || tab === 'announcements') {
                const notifData = await notificationsApi.getMyNotifications(unreadOnly, 0, 50);
                notifications = (notifData.notifications || []).map((n: any) => ({
                    id: n.id,
                    title: n.title,
                    message: n.message,
                    type: 'notification' as const,
                    notification_type: n.notification_type,
                    created_at: n.created_at,
                    is_read: n.is_read
                }));
            }

            if (tab === 'all' || tab === 'messages') {
                try {
                    const msgData = await messagesApi.getMyMessages(unreadOnly, 0, 50);
                    messages = (msgData.messages || []).map((m: any) => ({
                        id: m.id,
                        title: m.subject,
                        message: m.content,
                        type: 'message' as const,
                        sender_name: m.sender_name,
                        reason: m.reason,
                        created_at: m.created_at,
                        is_read: m.is_read
                    }));
                } catch (err) {
                    console.error('Failed to fetch messages:', err);
                }
            }

            // Combine and sort by date
            const combined = [...notifications, ...messages].sort((a, b) =>
                new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
            );

            setItems(combined);
        } catch (error) {
            console.error('Failed to fetch:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleMarkAsRead = async (item: NotificationItem) => {
        if (item.is_read) return;
        try {
            if (item.type === 'notification') {
                await notificationsApi.markAsRead(item.id);
            } else {
                await messagesApi.markAsRead(item.id);
            }
            setItems(prev =>
                prev.map(i => (i.id === item.id && i.type === item.type) ? { ...i, is_read: true } : i)
            );
        } catch (error) {
            console.error('Failed to mark as read:', error);
        }
    };

    const handleMarkAllRead = async () => {
        try {
            await Promise.all([
                notificationsApi.markAllAsRead(),
                messagesApi.markAllAsRead().catch(() => { })
            ]);
            setItems(prev => prev.map(i => ({ ...i, is_read: true })));
        } catch (error) {
            console.error('Failed to mark all as read:', error);
        }
    };

    const formatDate = (dateStr: string) => {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins} minutes ago`;
        if (diffHours < 24) return `${diffHours} hours ago`;
        if (diffDays < 7) return `${diffDays} days ago`;
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    const getIcon = (item: NotificationItem) => {
        if (item.type === 'message') return '✉️';
        const type = item.notification_type?.toUpperCase();
        if (type === 'ALERT') return '⚠️';
        if (type === 'INFO') return 'ℹ️';
        if (type === 'SYSTEM') return '⚙️';
        return '📢';
    };

    const unreadCount = items.filter(i => !i.is_read).length;

    return (
        <div className="notifications-page">
            <div className="notifications-header">
                <div>
                    <h1>Notifications & Messages</h1>
                    <p className="subtitle">Stay updated with announcements and personal messages</p>
                </div>
                <div className="header-actions">
                    {unreadCount > 0 && (
                        <button className="mark-all-btn" onClick={handleMarkAllRead}>
                            ✓ Mark all as read
                        </button>
                    )}
                </div>
            </div>

            {/* Tab Navigation */}
            <div className="notifications-tabs">
                <button
                    className={`tab-btn ${tab === 'all' ? 'active' : ''}`}
                    onClick={() => setTab('all')}
                >
                    📋 All
                </button>
                <button
                    className={`tab-btn ${tab === 'announcements' ? 'active' : ''}`}
                    onClick={() => setTab('announcements')}
                >
                    📢 Announcements
                </button>
                <button
                    className={`tab-btn ${tab === 'messages' ? 'active' : ''}`}
                    onClick={() => setTab('messages')}
                >
                    ✉️ Personal Messages
                </button>
            </div>

            <div className="notifications-filters">
                <button
                    className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
                    onClick={() => setFilter('all')}
                >
                    All
                </button>
                <button
                    className={`filter-btn ${filter === 'unread' ? 'active' : ''}`}
                    onClick={() => setFilter('unread')}
                >
                    Unread {unreadCount > 0 && <span className="count">{unreadCount}</span>}
                </button>
            </div>

            <div className="notifications-list">
                {loading ? (
                    <div className="loading">Loading...</div>
                ) : items.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">{tab === 'messages' ? '✉️' : '🔔'}</span>
                        <h3>No {tab === 'messages' ? 'Messages' : tab === 'announcements' ? 'Announcements' : 'Notifications'}</h3>
                        <p>{filter === 'unread' ? 'You have no unread items' : 'Nothing to show yet'}</p>
                    </div>
                ) : (
                    items.map(item => (
                        <div
                            key={`${item.type}-${item.id}`}
                            className={`notification-card ${!item.is_read ? 'unread' : ''}`}
                            onClick={() => handleMarkAsRead(item)}
                        >
                            <div className="notification-icon">
                                {getIcon(item)}
                            </div>
                            <div className="notification-body">
                                <div className="notification-header">
                                    <h4>{item.title}</h4>
                                    <span className="notification-time">{formatDate(item.created_at)}</span>
                                </div>
                                <p className="notification-message">{item.message}</p>
                                <div className="notification-meta">
                                    {item.type === 'message' ? (
                                        <>
                                            <span className="type-badge message">Personal Message</span>
                                            {item.sender_name && <span className="sender">From: {item.sender_name}</span>}
                                            {item.reason && <span className="reason">{item.reason}</span>}
                                        </>
                                    ) : (
                                        <span className={`type-badge ${item.notification_type?.toLowerCase()}`}>
                                            {item.notification_type || 'announcement'}
                                        </span>
                                    )}
                                    {!item.is_read && <span className="unread-badge">New</span>}
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

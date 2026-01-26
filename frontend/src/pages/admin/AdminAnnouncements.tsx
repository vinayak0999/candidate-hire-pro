import { useState, useEffect } from 'react';
import { notificationsApi } from '../../services/api';
import './AdminAnnouncements.css';

interface Notification {
    id: number;
    title: string;
    message: string;
    notification_type: string;
    target_audience: string;
    target_value: string | null;
    created_at: string;
    is_active: boolean;
    creator_name: string | null;
}

export default function AdminAnnouncements() {
    const [notifications, setNotifications] = useState<Notification[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [formData, setFormData] = useState({
        title: '',
        message: '',
        notification_type: 'ANNOUNCEMENT',
        target_audience: 'ALL',
        target_value: ''
    });
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    useEffect(() => {
        fetchNotifications();
    }, []);

    const fetchNotifications = async () => {
        try {
            setLoading(true);
            const data = await notificationsApi.getAllNotifications();
            setNotifications(data);
        } catch (err) {
            console.error('Failed to fetch notifications:', err);
            setError('Failed to load announcements');
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!formData.title.trim() || !formData.message.trim()) {
            setError('Title and message are required');
            return;
        }

        try {
            setSubmitting(true);
            setError(null);
            await notificationsApi.createNotification({
                title: formData.title,
                message: formData.message,
                notification_type: formData.notification_type,
                target_audience: formData.target_audience,
                target_value: formData.target_value || undefined
            });
            setSuccess('Announcement created successfully!');
            setFormData({ title: '', message: '', notification_type: 'ANNOUNCEMENT', target_audience: 'ALL', target_value: '' });
            setShowForm(false);
            fetchNotifications();
            setTimeout(() => setSuccess(null), 3000);
        } catch (err) {
            console.error('Failed to create notification:', err);
            setError('Failed to create announcement');
        } finally {
            setSubmitting(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this announcement?')) return;

        try {
            await notificationsApi.deleteNotification(id);
            setNotifications(prev => prev.filter(n => n.id !== id));
            setSuccess('Announcement deleted');
            setTimeout(() => setSuccess(null), 3000);
        } catch (err) {
            console.error('Failed to delete:', err);
            setError('Failed to delete announcement');
        }
    };

    const handleToggle = async (id: number) => {
        try {
            await notificationsApi.toggleNotification(id);
            setNotifications(prev => prev.map(n =>
                n.id === id ? { ...n, is_active: !n.is_active } : n
            ));
        } catch (err) {
            console.error('Failed to toggle:', err);
        }
    };

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const getTypeIcon = (type: string) => {
        switch (type.toUpperCase()) {
            case 'ALERT': return '⚠️';
            case 'INFO': return 'ℹ️';
            case 'SYSTEM': return '⚙️';
            default: return '📢';
        }
    };

    return (
        <div className="admin-announcements">
            <div className="announcements-header">
                <div>
                    <h1>Announcements</h1>
                    <p className="subtitle">Send announcements to all candidates or specific groups</p>
                </div>
                <button
                    className="create-btn"
                    onClick={() => setShowForm(!showForm)}
                >
                    {showForm ? 'Cancel' : '+ New Announcement'}
                </button>
            </div>

            {error && (
                <div className="message error">
                    <span>⚠️ {error}</span>
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {success && (
                <div className="message success">
                    <span>✅ {success}</span>
                </div>
            )}

            {showForm && (
                <div className="announcement-form-card">
                    <h3>Create New Announcement</h3>
                    <form onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label>Title *</label>
                            <input
                                type="text"
                                value={formData.title}
                                onChange={e => setFormData({ ...formData, title: e.target.value })}
                                placeholder="Announcement title..."
                                maxLength={200}
                            />
                        </div>

                        <div className="form-group">
                            <label>Message *</label>
                            <textarea
                                value={formData.message}
                                onChange={e => setFormData({ ...formData, message: e.target.value })}
                                placeholder="Write your announcement message..."
                                rows={4}
                            />
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Type</label>
                                <select
                                    value={formData.notification_type}
                                    onChange={e => setFormData({ ...formData, notification_type: e.target.value })}
                                >
                                    <option value="ANNOUNCEMENT">📢 Announcement</option>
                                    <option value="INFO">ℹ️ Information</option>
                                    <option value="ALERT">⚠️ Alert</option>
                                    <option value="SYSTEM">⚙️ System</option>
                                </select>
                            </div>

                            <div className="form-group">
                                <label>Target Audience</label>
                                <select
                                    value={formData.target_audience}
                                    onChange={e => setFormData({ ...formData, target_audience: e.target.value })}
                                >
                                    <option value="ALL">All Candidates</option>
                                    <option value="BATCH">Specific Batch</option>
                                    <option value="BRANCH">Specific Branch</option>
                                </select>
                            </div>
                        </div>

                        {formData.target_audience !== 'ALL' && (
                            <div className="form-group">
                                <label>
                                    {formData.target_audience === 'BATCH' ? 'Batch Year' : 'Branch Name'} *
                                </label>
                                <input
                                    type="text"
                                    value={formData.target_value}
                                    onChange={e => setFormData({ ...formData, target_value: e.target.value })}
                                    placeholder={formData.target_audience === 'BATCH' ? 'e.g., 2025' : 'e.g., Computer Science'}
                                />
                            </div>
                        )}

                        <div className="form-actions">
                            <button type="button" className="cancel-btn" onClick={() => setShowForm(false)}>
                                Cancel
                            </button>
                            <button type="submit" className="submit-btn" disabled={submitting}>
                                {submitting ? 'Creating...' : 'Create Announcement'}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            <div className="announcements-list">
                {loading ? (
                    <div className="loading">Loading announcements...</div>
                ) : notifications.length === 0 ? (
                    <div className="empty-state">
                        <span className="empty-icon">📭</span>
                        <h3>No Announcements Yet</h3>
                        <p>Create your first announcement to notify candidates</p>
                    </div>
                ) : (
                    notifications.map(notif => (
                        <div key={notif.id} className={`announcement-card ${!notif.is_active ? 'inactive' : ''}`}>
                            <div className="announcement-header">
                                <div className="announcement-icon">{getTypeIcon(notif.notification_type)}</div>
                                <div className="announcement-meta">
                                    <h4>{notif.title}</h4>
                                    <div className="meta-info">
                                        <span className="date">{formatDate(notif.created_at)}</span>
                                        <span className="audience">
                                            {notif.target_audience.toUpperCase() === 'ALL' ? '👥 All Candidates' :
                                                notif.target_audience.toUpperCase() === 'BATCH' ? `📅 Batch: ${notif.target_value}` :
                                                    `📚 Branch: ${notif.target_value}`}
                                        </span>
                                        {!notif.is_active && <span className="status inactive">Inactive</span>}
                                    </div>
                                </div>
                                <div className="announcement-actions">
                                    <button
                                        className={`toggle-btn ${notif.is_active ? 'active' : ''}`}
                                        onClick={() => handleToggle(notif.id)}
                                        title={notif.is_active ? 'Deactivate' : 'Activate'}
                                    >
                                        {notif.is_active ? '✓' : '○'}
                                    </button>
                                    <button
                                        className="delete-btn"
                                        onClick={() => handleDelete(notif.id)}
                                        title="Delete"
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </div>
                            <p className="announcement-message">{notif.message}</p>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

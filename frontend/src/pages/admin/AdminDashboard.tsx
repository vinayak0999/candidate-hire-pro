import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminApiService } from '../../services/api';
import './AdminDashboard.css';

// Stats interface
interface DashboardStats {
    total_candidates: number;
    active_jobs: number;
    tests_completed: number;
    flagged_attempts: number;
    mcq_pass_rate: number;
    text_annotation_pass_rate: number;
    image_annotation_pass_rate: number;
    video_annotation_pass_rate: number;
}

// Stats Card Component
interface StatCardProps {
    title: string;
    value: string | number;
    change?: string;
    trend?: 'up' | 'down';
    icon: React.ReactNode;
    color: string;
}

const StatCard = ({ title, value, change, trend, icon, color }: StatCardProps) => (
    <div className="stat-card">
        <div className="stat-icon" style={{ background: color }}>
            {icon}
        </div>
        <div className="stat-content">
            <span className="stat-title">{title}</span>
            <span className="stat-value">{value}</span>
            {change && (
                <span className={`stat-change ${trend}`}>
                    {trend === 'up' ? '↑' : '↓'} {change}
                </span>
            )}
        </div>
    </div>
);

// Recent Activity Item
interface ActivityItem {
    id: number;
    user: string;
    action: string;
    time: string;
    status: 'completed' | 'pending' | 'flagged';
}

// Activities will be fetched from API (currently empty)
const recentActivities: ActivityItem[] = [];

export default function AdminDashboard() {
    const navigate = useNavigate();
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchStats();
    }, []);

    const fetchStats = async () => {
        try {
            const data = await adminApiService.getStats();
            setStats(data);
        } catch (error) {
            console.error('Failed to fetch stats:', error);
            // Set fallback data
            setStats({
                total_candidates: 0,
                active_jobs: 0,
                tests_completed: 0,
                flagged_attempts: 0,
                mcq_pass_rate: 0,
                text_annotation_pass_rate: 0,
                image_annotation_pass_rate: 0,
                video_annotation_pass_rate: 0
            });
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="admin-dashboard">
                <div className="loading-state">Loading dashboard...</div>
            </div>
        );
    }

    return (
        <div className="admin-dashboard">
            <div className="admin-header">
                <div>
                    <h1 className="admin-title">Dashboard</h1>
                    <p className="admin-subtitle">Welcome back! Here's what's happening today.</p>
                </div>
                <div className="admin-header-actions">
                    <button className="btn-secondary">Export Report</button>
                    <button className="btn-primary" onClick={() => navigate('/admin/test-generator')}>+ Create Test</button>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
                <StatCard
                    title="Total Candidates"
                    value={stats?.total_candidates.toLocaleString() || '0'}
                    color="linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%)"
                    icon={
                        <svg viewBox="0 0 24 24" fill="white">
                            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5z" />
                        </svg>
                    }
                />
                <StatCard
                    title="Active Jobs"
                    value={stats?.active_jobs || '0'}
                    color="linear-gradient(135deg, #10b981 0%, #059669 100%)"
                    icon={
                        <svg viewBox="0 0 24 24" fill="white">
                            <path d="M20 6h-4V4c0-1.11-.89-2-2-2h-4c-1.11 0-2 .89-2 2v2H4c-1.11 0-2 .89-2 2v11c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V8c0-1.11-.89-2-2-2zm-6 0h-4V4h4v2z" />
                        </svg>
                    }
                />
                <StatCard
                    title="Tests Completed"
                    value={stats?.tests_completed.toLocaleString() || '0'}
                    color="linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"
                    icon={
                        <svg viewBox="0 0 24 24" fill="white">
                            <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z" />
                        </svg>
                    }
                />
                <StatCard
                    title="Flagged Attempts"
                    value={stats?.flagged_attempts || '0'}
                    color="linear-gradient(135deg, #ef4444 0%, #dc2626 100%)"
                    icon={
                        <svg viewBox="0 0 24 24" fill="white">
                            <path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6z" />
                        </svg>
                    }
                />
            </div>

            {/* Main Content Grid */}
            <div className="dashboard-grid">
                {/* Recent Activity */}
                <div className="dashboard-card activity-card">
                    <div className="card-header">
                        <h3>Recent Activity</h3>
                        <a href="#" className="view-all">View all</a>
                    </div>
                    <div className="activity-list">
                        {recentActivities.length === 0 ? (
                            <div className="empty-activity">No recent activity</div>
                        ) : (
                            recentActivities.map(activity => (
                                <div key={activity.id} className="activity-item">
                                    <div className="activity-avatar">
                                        {activity.user.split(' ').map(n => n[0]).join('')}
                                    </div>
                                    <div className="activity-content">
                                        <span className="activity-user">{activity.user}</span>
                                        <span className="activity-action">{activity.action}</span>
                                    </div>
                                    <div className="activity-meta">
                                        <span className="activity-time">{activity.time}</span>
                                        <span className={`activity-status ${activity.status}`}>
                                            {activity.status}
                                        </span>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Quick Stats */}
                <div className="dashboard-card quick-stats-card">
                    <div className="card-header">
                        <h3>Test Performance</h3>
                    </div>
                    <div className="quick-stats">
                        <div className="quick-stat-item">
                            <div className="quick-stat-bar">
                                <div className="bar-fill" style={{ width: `${stats?.mcq_pass_rate || 0}%`, background: '#10b981' }}></div>
                            </div>
                            <div className="quick-stat-info">
                                <span>MCQ Assessments</span>
                                <span className="quick-stat-value">{stats?.mcq_pass_rate || 0}% pass rate</span>
                            </div>
                        </div>
                        <div className="quick-stat-item">
                            <div className="quick-stat-bar">
                                <div className="bar-fill" style={{ width: `${stats?.text_annotation_pass_rate || 0}%`, background: '#1E40AF' }}></div>
                            </div>
                            <div className="quick-stat-info">
                                <span>Text Annotation</span>
                                <span className="quick-stat-value">{stats?.text_annotation_pass_rate || 0}% pass rate</span>
                            </div>
                        </div>
                        <div className="quick-stat-item">
                            <div className="quick-stat-bar">
                                <div className="bar-fill" style={{ width: `${stats?.image_annotation_pass_rate || 0}%`, background: '#f59e0b' }}></div>
                            </div>
                            <div className="quick-stat-info">
                                <span>Image Annotation</span>
                                <span className="quick-stat-value">{stats?.image_annotation_pass_rate || 0}% pass rate</span>
                            </div>
                        </div>
                        <div className="quick-stat-item">
                            <div className="quick-stat-bar">
                                <div className="bar-fill" style={{ width: `${stats?.video_annotation_pass_rate || 0}%`, background: '#ec4899' }}></div>
                            </div>
                            <div className="quick-stat-info">
                                <span>Video Annotation</span>
                                <span className="quick-stat-value">{stats?.video_annotation_pass_rate || 0}% pass rate</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

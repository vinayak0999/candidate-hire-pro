import { useState, useEffect } from 'react';
import { jobsApi } from '../services/api';
import type { User, Job, JobStats } from '../types';
import './Dashboard.css';

type TabType = 'skill' | 'course' | 'jobs';

interface DashboardProps {
    user: User | null;
}

export default function Dashboard({ user }: DashboardProps) {
    const [activeTab, setActiveTab] = useState<TabType>('skill');
    const [jobs, setJobs] = useState<Job[]>([]);
    const [stats, setStats] = useState<JobStats | null>(null);
    const [loadingJobs, setLoadingJobs] = useState(false);

    // Fetch jobs/stats when jobs tab is active
    useEffect(() => {
        if (activeTab === 'jobs') {
            loadJobs();
            loadStats();
        }
    }, [activeTab]);

    const loadJobs = async () => {
        setLoadingJobs(true);
        try {
            const data = await jobsApi.getAll();
            setJobs(data);
        } catch (error) {
            console.error('Failed to load jobs:', error);
        } finally {
            setLoadingJobs(false);
        }
    };

    const loadStats = async () => {
        try {
            const data = await jobsApi.getStats();
            setStats(data);
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    };

    const solvedEasy = user?.solved_easy || 1245;
    const solvedMedium = user?.solved_medium || 1754;
    const solvedHard = user?.solved_hard || 514;
    const totalSolved = solvedEasy + solvedMedium + solvedHard;
    const totalQuestions = 4616;
    const percentage = (totalSolved / totalQuestions) * 100;

    // Donut chart logic
    const radius = 45;
    const circumference = 2 * Math.PI * radius;
    const strokeDasharray = (percentage / 100) * circumference;

    return (
        <div className="dashboard">
            <div className="dashboard-header">
                <div>
                    <h1 className="dashboard-title">Dashboard</h1>
                    <p className="dashboard-subtitle">Welcome back, {user?.name?.split(' ')[0] || 'User'}</p>
                </div>
                <div className="dashboard-date">
                    {new Date().toLocaleDateString('en-US', {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    })}
                </div>
            </div>

            {/* Profile Section - Enhanced Design */}
            <div className="user-card glass-panel">
                <div className="user-card-banner" />
                <div className="user-card-content">
                    <div className="user-avatar-wrapper">
                        <img
                            src={user?.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.name || 'User')}&size=140&background=1E3A8A&color=fff`}
                            alt="Profile"
                            className="user-avatar"
                        />
                    </div>
                    <div className="user-info">
                        <h2 className="user-name">{user?.name || 'Vinayak Ji Shukla'}</h2>
                        <p className="user-email">{user?.email || 'vinayak.shukla2021@vitstudent.ac.in'}</p>

                        <div className="user-tags">
                            <span className="info-tag">🎓 {user?.degree || 'B.Tech'} - {user?.branch || 'CSE'}</span>
                            <span className="info-tag">📍 {user?.college || 'VIT Vellore'}</span>
                            <span className="info-tag">🆔 {user?.registration_number || '21BCE7920'}</span>
                        </div>
                    </div>
                    <div className="user-batch-badge">
                        <span>Batch {user?.batch || '2025'}</span>
                    </div>
                </div>
            </div>

            {/* Navigation Tabs - Glass Pill Style */}
            <div className="dashboard-tabs-container">
                <div className="dashboard-tabs glass-panel">
                    <button
                        className={`dashboard-tab ${activeTab === 'skill' ? 'active' : ''}`}
                        onClick={() => setActiveTab('skill')}
                    >
                        Skill & Assessment
                    </button>
                    <button
                        className={`dashboard-tab ${activeTab === 'course' ? 'active' : ''}`}
                        onClick={() => setActiveTab('course')}
                    >
                        Courses
                    </button>
                    <button
                        className={`dashboard-tab ${activeTab === 'jobs' ? 'active' : ''}`}
                        onClick={() => setActiveTab('jobs')}
                    >
                        Opportunities
                    </button>
                </div>
            </div>

            {/* Tab Content Areas */}
            <div className="tab-content">
                {activeTab === 'skill' && (
                    <div className="stats-grid">
                        <div className="stat-card glass-panel highlight-card">
                            <div className="stat-card-header">
                                <h3 className="stat-card-title">Neo-PAT Score</h3>
                            </div>
                            <div className="stat-main-value">{user?.neo_pat_score || 1324}</div>
                            <p className="stat-desc">Top 5% of your batch</p>
                        </div>

                        <div className="stat-card glass-panel">
                            <div className="stat-card-header">
                                <h3 className="stat-card-title">Problem Solving</h3>
                            </div>
                            <div className="solved-visual">
                                <div className="chart-container">
                                    <svg viewBox="0 0 100 100" className="chart-svg">
                                        <circle cx="50" cy="50" r={radius} className="chart-bg" />
                                        <circle
                                            cx="50"
                                            cy="50"
                                            r={radius}
                                            className="chart-fill"
                                            strokeDasharray={`${strokeDasharray} ${circumference}`}
                                        />
                                    </svg>
                                    <div className="chart-text">
                                        <span className="chart-value">{totalSolved}</span>
                                        <span className="chart-label">Solved</span>
                                    </div>
                                </div>
                                <div className="solved-legend">
                                    <div className="legend-item"><span className="dot easy"></span>Easy: {solvedEasy}</div>
                                    <div className="legend-item"><span className="dot medium"></span>Medium: {solvedMedium}</div>
                                    <div className="legend-item"><span className="dot hard"></span>Hard: {solvedHard}</div>
                                </div>
                            </div>
                        </div>

                        <div className="stat-card glass-panel">
                            <div className="stat-card-header">
                                <h3 className="stat-card-title">Neo-Colab</h3>
                            </div>
                            <div className="badges-row">
                                <div className="badge-stat">
                                    <span className="b-val">{user?.total_badges || 3}</span>
                                    <span className="b-label">Badges</span>
                                </div>
                                <div className="badge-stat">
                                    <span className="b-val">{user?.total_certificates || 5}</span>
                                    <span className="b-label">Certificates</span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'course' && (
                    <div className="stats-grid">
                        <div className="stat-card glass-panel">
                            <h3>Active Courses</h3>
                            <div className="stat-main-value">2</div>
                            <p className="stat-desc">In Progress</p>
                        </div>
                        <div className="stat-card glass-panel">
                            <h3>Completed</h3>
                            <div className="stat-main-value">12</div>
                            <p className="stat-desc">Certified</p>
                        </div>
                    </div>
                )}

                {activeTab === 'jobs' && (
                    <div className="jobs-section-wrapper">
                        {/* Stats Summary Row */}
                        <div className="jobs-stats-row">
                            <div className="j-stat glass-panel">
                                <span className="js-label">Active Jobs</span>
                                <span className="js-val">{stats?.total_jobs || jobs.length || 0}</span>
                            </div>
                            <div className="j-stat glass-panel">
                                <span className="js-label">Applied</span>
                                <span className="js-val">{stats?.applied || 0}</span>
                            </div>
                            <div className="j-stat glass-panel">
                                <span className="js-label">Rejected</span>
                                <span className="js-val error">{stats?.rejected || 0}</span>
                            </div>
                        </div>

                        {loadingJobs ? (
                            <div className="loading-state">Loading Opportunities...</div>
                        ) : (
                            <div className="jobs-grid-simple">
                                {jobs.map(job => (
                                    <div key={job.id} className="job-card-simple glass-panel">
                                        <div className="jc-header">
                                            <div className="jc-logo">{job.company_name.charAt(0)}</div>
                                            <div>
                                                <h4>{job.role}</h4>
                                                <p>{job.company_name}</p>
                                            </div>
                                        </div>
                                        <div className="jc-tags">
                                            <span>{job.location}</span>
                                            <span className="highlight">{job.ctc} LPA</span>
                                        </div>
                                        <button className="btn-apply-small">View</button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

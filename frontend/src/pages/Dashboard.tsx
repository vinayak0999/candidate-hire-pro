import { useState, useEffect } from 'react';
import { jobsApi } from '../services/api';
import type { User, Job } from '../types';
import './Dashboard.css';

interface DashboardProps {
    user: User | null;
}

type TabType = 'skill' | 'course' | 'jobs';

export default function Dashboard({ user }: DashboardProps) {
    const [activeTab, setActiveTab] = useState<TabType>('skill');
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loadingJobs, setLoadingJobs] = useState(false);

    // Fetch jobs when jobs tab is active
    useEffect(() => {
        if (activeTab === 'jobs') {
            fetchJobs();
        }
    }, [activeTab]);

    const fetchJobs = async () => {
        try {
            setLoadingJobs(true);
            const data = await jobsApi.getAll();
            setJobs(data);
        } catch (error) {
            console.error('Failed to fetch jobs:', error);
        } finally {
            setLoadingJobs(false);
        }
    };

    const solvedEasy = user?.solved_easy || 1245;
    const solvedMedium = user?.solved_medium || 1754;
    const solvedHard = user?.solved_hard || 514;
    const totalSolved = solvedEasy + solvedMedium + solvedHard;
    const totalQuestions = 4616;
    const percentage = (totalSolved / totalQuestions) * 100;

    // Calculate stroke dasharray for the donut chart
    const radius = 45;
    const circumference = 2 * Math.PI * radius;
    const strokeDasharray = (percentage / 100) * circumference;

    return (
        <div className="dashboard">
            <div className="dashboard-header">
                <h1 className="dashboard-title">Dashboard</h1>
                <div className="dashboard-date">
                    Last Updated on {new Date().toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                    })} {new Date().toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit'
                    })}
                </div>
            </div>

            {/* User Card */}
            <div className="user-card">
                <div className="user-card-banner" />
                <div className="user-card-content">
                    <div className="user-avatar-wrapper">
                        <img
                            src={user?.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.name || 'User')}&size=120&background=4361EE&color=fff`}
                            alt="Profile"
                            className="user-avatar"
                        />
                    </div>
                    <div className="user-info">
                        <h2 className="user-name">{user?.name || 'User'}</h2>
                        <p className="user-email">{user?.email}</p>

                        <div className="user-details">
                            <div className="user-detail">
                                <span className="user-detail-label">Register Number</span>
                                <span className="user-detail-value">{user?.registration_number || '21BCE7920'}</span>
                            </div>
                            <div className="user-detail">
                                <span className="user-detail-label">Degree</span>
                                <span className="user-detail-value">{user?.degree || 'B.Tech'} - {user?.branch || 'CSE'}</span>
                            </div>
                            <div className="user-detail">
                                <span className="user-detail-label">Batch</span>
                                <span className="user-detail-value">{user?.batch || '2021-2025'}</span>
                            </div>
                            <div className="user-detail">
                                <span className="user-detail-label">College</span>
                                <span className="user-detail-value">{user?.college || 'VIT Vellore'}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="dashboard-tabs">
                <button
                    className={`dashboard-tab ${activeTab === 'skill' ? 'active' : ''}`}
                    onClick={() => setActiveTab('skill')}
                >
                    Skill
                </button>
                <button
                    className={`dashboard-tab ${activeTab === 'course' ? 'active' : ''}`}
                    onClick={() => setActiveTab('course')}
                >
                    Course
                </button>
                <button
                    className={`dashboard-tab ${activeTab === 'jobs' ? 'active' : ''}`}
                    onClick={() => setActiveTab('jobs')}
                >
                    Jobs
                </button>
            </div>

            {/* Tab Content */}
            {activeTab === 'skill' && (
                <div className="stats-section">
                    <div className="stat-card">
                        <div className="stat-card-header">
                            <h3 className="stat-card-title">Neo-PAT</h3>
                            <span className="stat-card-badge">Score</span>
                        </div>
                        <div className="stat-value">{user?.neo_pat_score || 1324}</div>
                        <div className="stat-label">Your Assessment Score</div>
                    </div>

                    <div className="stat-card">
                        <div className="stat-card-header">
                            <h3 className="stat-card-title">Solved Questions</h3>
                        </div>
                        <div className="solved-questions">
                            <div className="solved-chart">
                                <svg viewBox="0 0 100 100">
                                    <circle
                                        cx="50"
                                        cy="50"
                                        r={radius}
                                        fill="none"
                                        stroke="#e5e7eb"
                                        strokeWidth="8"
                                    />
                                    <circle
                                        cx="50"
                                        cy="50"
                                        r={radius}
                                        fill="none"
                                        stroke="#4361EE"
                                        strokeWidth="8"
                                        strokeDasharray={`${strokeDasharray} ${circumference}`}
                                        strokeLinecap="round"
                                    />
                                </svg>
                                <div className="solved-chart-center">
                                    <span className="solved-total">{totalSolved}</span>
                                    <span className="solved-label">Solved</span>
                                </div>
                            </div>

                            <div className="solved-breakdown">
                                <div className="solved-item">
                                    <div className="solved-dot easy"></div>
                                    <div className="solved-item-info">
                                        <span className="solved-item-label">Easy</span>
                                        <span className="solved-item-value">{solvedEasy}/1639</span>
                                    </div>
                                </div>
                                <div className="solved-item">
                                    <div className="solved-dot medium"></div>
                                    <div className="solved-item-info">
                                        <span className="solved-item-label">Medium</span>
                                        <span className="solved-item-value">{solvedMedium}/2366</span>
                                    </div>
                                </div>
                                <div className="solved-item">
                                    <div className="solved-dot hard"></div>
                                    <div className="solved-item-info">
                                        <span className="solved-item-label">Hard</span>
                                        <span className="solved-item-value">{solvedHard}/611</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="stat-card">
                        <div className="stat-card-header">
                            <h3 className="stat-card-title">Neo-Colab</h3>
                        </div>
                        <div className="quick-stats">
                            <div className="quick-stat">
                                <div className="quick-stat-value">{user?.total_badges || 3}</div>
                                <div className="quick-stat-label">Badges Earned</div>
                            </div>
                            <div className="quick-stat">
                                <div className="quick-stat-value">{user?.total_certificates || 2}</div>
                                <div className="quick-stat-label">Certificates</div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {activeTab === 'course' && (
                <div className="stats-section">
                    <div className="stat-card">
                        <div className="stat-card-header">
                            <h3 className="stat-card-title">Enrolled Courses</h3>
                        </div>
                        <div className="stat-value">5</div>
                        <div className="stat-label">Active Courses</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card-header">
                            <h3 className="stat-card-title">Completed Courses</h3>
                        </div>
                        <div className="stat-value">12</div>
                        <div className="stat-label">Courses Finished</div>
                    </div>
                </div>
            )}

            {activeTab === 'jobs' && (
                <div className="jobs-section">
                    {loadingJobs ? (
                        <div className="loading-jobs">Loading jobs...</div>
                    ) : jobs.length === 0 ? (
                        <div className="no-jobs">
                            <span className="no-jobs-icon">📋</span>
                            <h3>No Active Job Postings</h3>
                            <p>Check back later for new opportunities</p>
                        </div>
                    ) : (
                        <div className="jobs-grid">
                            {jobs.map(job => (
                                <div key={job.id} className="job-card">
                                    <div className="job-card-header">
                                        <div className="job-company-logo">
                                            {job.company_name?.charAt(0) || 'A'}
                                        </div>
                                        <div className="job-info">
                                            <h3 className="job-title">{job.role}</h3>
                                            <p className="job-company">{job.company_name}</p>
                                        </div>
                                    </div>
                                    <div className="job-details">
                                        {job.location && (
                                            <span className="job-tag">📍 {job.location}</span>
                                        )}
                                        {job.job_type && (
                                            <span className="job-tag">💼 {job.job_type}</span>
                                        )}
                                        {job.ctc && (
                                            <span className="job-tag">💰 {job.ctc} LPA</span>
                                        )}
                                    </div>
                                    <button className="job-apply-btn">Apply Now</button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

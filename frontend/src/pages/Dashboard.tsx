import { useState, useEffect } from 'react';
import { jobsApi, profileApi } from '../services/api';
import type { User, Job, JobStats } from '../types';
import './Dashboard.css';
import profileBanner from '../assets/banner.jpg';

type TabType = 'skill' | 'course' | 'jobs';

interface DashboardProps {
    user: User | null;
}

interface Education {
    id: number;
    school: string;
    degree: string | null;
    field_of_study: string | null;
    start_year: number | null;
    end_year: number | null;
    gpa: string | null;
}

interface Skill {
    id: number;
    name: string;
    display_name: string;
    category: string | null;
}

interface CandidateProfile {
    professional_summary: string | null;
    current_role: string | null;
    current_company: string | null;
    years_of_experience: number | null;
    education: Education[];
    skills: Skill[];
    linkedin_url: string | null;
    github_url: string | null;
}

export default function Dashboard({ user }: DashboardProps) {
    const [activeTab, setActiveTab] = useState<TabType>('skill');
    const [jobs, setJobs] = useState<Job[]>([]);
    const [stats, setStats] = useState<JobStats | null>(null);
    const [loadingJobs, setLoadingJobs] = useState(false);
    const [profile, setProfile] = useState<CandidateProfile | null>(null);

    useEffect(() => {
        fetchProfile();
    }, []);

    useEffect(() => {
        if (activeTab === 'jobs') {
            loadJobs();
            loadStats();
        }
    }, [activeTab]);

    const fetchProfile = async () => {
        try {
            const data = await profileApi.getMyProfile();
            setProfile(data);
        } catch (error) {
            console.error('Failed to load profile:', error);
        }
    };

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

    const solvedEasy = user?.solved_easy || 0;
    const solvedMedium = user?.solved_medium || 0;
    const solvedHard = user?.solved_hard || 0;
    const totalSolved = solvedEasy + solvedMedium + solvedHard;
    const totalQuestions = 4616;
    const percentage = totalQuestions > 0 ? (totalSolved / totalQuestions) * 100 : 0;

    const radius = 45;
    const circumference = 2 * Math.PI * radius;
    const strokeDasharray = (percentage / 100) * circumference;

    const latestEducation = profile?.education?.[0] || null;
    const profileSkills = profile?.skills || [];

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

            {/* Profile Section - Original Structure */}
            <div className="user-card glass-panel">
                <div className="user-card-banner" style={{ backgroundImage: `url(${profileBanner})` }} />
                <div className="user-card-content">
                    <div className="user-avatar-wrapper">
                        <img
                            src={user?.avatar_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(user?.name || 'User')}&size=140&background=1E3A8A&color=fff`}
                            alt="Profile"
                            className="user-avatar"
                        />
                        {/* Social Links */}
                        {(profile?.linkedin_url || profile?.github_url) && (
                            <div className="user-social-links">
                                {profile?.linkedin_url && (
                                    <a href={profile.linkedin_url} target="_blank" rel="noopener noreferrer" className="social-btn linkedin" title="LinkedIn">
                                        <svg viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.32 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.79M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/>
                                        </svg>
                                    </a>
                                )}
                                {profile?.github_url && (
                                    <a href={profile.github_url} target="_blank" rel="noopener noreferrer" className="social-btn github" title="GitHub">
                                        <svg viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M12 2A10 10 0 0 0 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0 0 12 2z"/>
                                        </svg>
                                    </a>
                                )}
                            </div>
                        )}
                    </div>
                    <div className="user-info">
                        <h2 className="user-name">{user?.name || 'User'}</h2>
                        {profile?.current_role && (
                            <p className="user-title">{profile.current_role}</p>
                        )}
                        <p className="user-email">{user?.email}</p>

                        <div className="user-tags">
                            {(latestEducation?.degree || user?.degree || user?.branch) && (
                                <span className="info-tag">🎓 {latestEducation?.degree || [user?.degree, user?.branch].filter(Boolean).join(' - ')}</span>
                            )}
                            {(latestEducation?.school || user?.college) && (
                                <span className="info-tag">🏫 {latestEducation?.school || user?.college}</span>
                            )}
                            {profile?.current_company && (
                                <span className="info-tag">🏢 {profile.current_company}</span>
                            )}
                            {profile?.years_of_experience !== null && profile?.years_of_experience !== undefined && profile.years_of_experience > 0 && (
                                <span className="info-tag">⏳ {profile.years_of_experience} {profile.years_of_experience === 1 ? 'year' : 'years'} exp</span>
                            )}
                        </div>

                        {/* Professional Summary */}
                        {profile?.professional_summary && (
                            <div className="user-summary">
                                <p className="user-summary-text">{profile.professional_summary}</p>
                            </div>
                        )}
                    </div>
                    {(user?.batch || latestEducation?.end_year) && (
                        <div className="user-batch-badge">
                            <span>Batch {latestEducation?.end_year || user?.batch}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Navigation Tabs */}
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

            {/* Tab Content */}
            <div className="tab-content">
                {activeTab === 'skill' && (
                    <div className="stats-grid">
                        <div className="stat-card glass-panel highlight-card">
                            <div className="stat-card-header">
                                <h3 className="stat-card-title">Neo-PAT Score</h3>
                            </div>
                            <div className="stat-main-value">{user?.neo_pat_score || 0}</div>
                            {(user?.neo_pat_score || 0) > 0 && (
                                <p className="stat-desc">Top 5% of your batch</p>
                            )}
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
                                    <span className="b-val">{user?.badges_count || 0}</span>
                                    <span className="b-label">Badges</span>
                                </div>
                                <div className="badge-stat">
                                    <span className="b-val">{user?.super_badges_count || 0}</span>
                                    <span className="b-label">Super Badges</span>
                                </div>
                            </div>
                        </div>

                        {/* Skills Card */}
                        {profileSkills.length > 0 && (
                            <div className="stat-card glass-panel skills-card">
                                <div className="stat-card-header">
                                    <h3 className="stat-card-title">My Skills</h3>
                                </div>
                                <div className="skills-grid">
                                    {profileSkills.map(skill => (
                                        <span key={skill.id} className="skill-chip">{skill.display_name}</span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'course' && (
                    <div className="stats-grid">
                        <div className="stat-card glass-panel">
                            <h3>Active Courses</h3>
                            <div className="stat-main-value">0</div>
                            <p className="stat-desc-muted">In Progress</p>
                        </div>
                        <div className="stat-card glass-panel">
                            <h3>Completed</h3>
                            <div className="stat-main-value">0</div>
                            <p className="stat-desc-muted">Certified</p>
                        </div>
                    </div>
                )}

                {activeTab === 'jobs' && (
                    <div className="jobs-section-wrapper">
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
                        ) : jobs.length === 0 ? (
                            <div className="empty-jobs-state glass-panel">
                                <span className="empty-icon">📋</span>
                                <p>No opportunities available at the moment.</p>
                            </div>
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
                                            <span>{job.location || 'Remote'}</span>
                                            <span className="highlight">{job.ctc || 0} LPA</span>
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

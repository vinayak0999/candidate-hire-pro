import { useState, useEffect, useCallback } from 'react';
import { profileApi } from '../services/api';
import type { User } from '../types';
import './Profile.css';

interface ProfileProps {
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

interface WorkExperience {
    id: number;
    company: string;
    role: string;
    city: string | null;
    country: string | null;
    start_date: string | null;
    end_date: string | null;
    is_current: boolean;
    description: string | null;
}

interface Project {
    id: number;
    name: string;
    description: string | null;
    technologies: string[];
    start_year: number | null;
    end_year: number | null;
    url: string | null;
}

interface Skill {
    id: number;
    name: string;
    display_name: string;
    category: string | null;
}

interface CandidateProfile {
    id: number;
    user_id: number;
    resume_filename: string | null;
    professional_summary: string | null;
    linkedin_url: string | null;
    github_url: string | null;
    years_of_experience: number | null;
    current_role: string | null;
    current_company: string | null;
    education: Education[];
    work_experience: WorkExperience[];
    projects: Project[];
    skills: Skill[];
    // Wizard data
    has_data_annotation_experience: boolean | null;
    why_annotation: string | null;
}

// Helper function to parse bullet points from description
const parseBulletPoints = (text: string | null): string[] => {
    if (!text) return [];
    // Split by common bullet separators: |, •, -, or newlines
    const bullets = text
        .split(/[|•\n]|\s[-–]\s/)
        .map(b => b.trim())
        .filter(b => b.length > 0);
    return bullets;
};

// Generate modern avatar URL (Unified with Dashboard)
const getAvatarUrl = (name: string | undefined) => {
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(name || 'User')}&size=140&background=1E3A8A&color=fff`;
};

const tabs = [
    { id: 'academic', label: 'Academic', icon: '🎓' },
    { id: 'experience', label: 'Experience', icon: '💼' },
    { id: 'resume', label: 'Resume', icon: '📄' },
    { id: 'skills', label: 'Skills & Projects', icon: '⚡' },
    { id: 'settings', label: 'Settings', icon: '⚙️' }
];

export default function Profile({ user }: ProfileProps) {
    const [activeTab, setActiveTab] = useState('academic');
    const [profile, setProfile] = useState<CandidateProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [dragActive, setDragActive] = useState(false);

    useEffect(() => {
        fetchProfile();
    }, []);

    const fetchProfile = async () => {
        try {
            const data = await profileApi.getMyProfile();
            setProfile(data);
        } catch (err: any) {
            if (err.response?.status !== 404) {
                console.error('Failed to load profile:', err);
            }
        } finally {
            setLoading(false);
        }
    };

    const handleUpload = async (file: File) => {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            setError('Please upload a PDF file');
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            setError('File size must be less than 10MB');
            return;
        }

        try {
            setUploading(true);
            setUploadProgress(10);
            setError(null);

            const progressInterval = setInterval(() => {
                setUploadProgress(prev => Math.min(prev + 10, 90));
            }, 500);

            // Backend parses synchronously and updates profile
            await profileApi.uploadResume(file);

            clearInterval(progressInterval);
            setUploadProgress(100);

            // Refetch profile immediately - backend processes synchronously now
            try {
                const data = await profileApi.getMyProfile();
                setProfile(data);
            } catch (e) {
                console.error('Failed to refetch profile:', e);
            }

            setTimeout(() => setUploadProgress(0), 1000);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to upload resume');
        } finally {
            setUploading(false);
        }
    };

    const handleDrag = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleUpload(e.dataTransfer.files[0]);
        }
    }, []);

    const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            handleUpload(e.target.files[0]);
        }
    };

    // Render Tab Content
    const renderTabContent = () => {
        if (loading) {
            return (
                <div className="loading-container">
                    <div className="loading-spinner"></div>
                    <p className="loading-text">Loading your profile...</p>
                </div>
            );
        }

        switch (activeTab) {
            case 'academic':
                return (
                    <div className="tab-panel">
                        <div className="tab-panel-header">
                            <h3>🎓 Academic Information</h3>
                        </div>
                        {profile?.education && profile.education.length > 0 ? (
                            <div className="entries-list">
                                {profile.education.map(edu => (
                                    <div key={edu.id} className="entry-card">
                                        <div className="entry-header">
                                            <div>
                                                <h4 className="entry-title">{edu.school}</h4>
                                                <p className="entry-subtitle">
                                                    {edu.degree}
                                                    {edu.field_of_study && !edu.degree?.toLowerCase().includes(edu.field_of_study.toLowerCase()) && ` in ${edu.field_of_study}`}
                                                </p>
                                            </div>
                                            {edu.gpa && (
                                                <span className="entry-badge">GPA: {edu.gpa}</span>
                                            )}
                                        </div>
                                        <div className="entry-meta">
                                            <span className="entry-date">
                                                📅 {edu.start_year} - {edu.end_year || 'Present'}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="empty-state">
                                <span className="empty-state-icon">📚</span>
                                <h4 className="empty-state-title">No Education Data</h4>
                                <p className="empty-state-text">Upload your resume to automatically populate your education history.</p>
                            </div>
                        )}
                    </div>
                );

            case 'experience':
                return (
                    <div className="tab-panel">
                        <div className="tab-panel-header">
                            <h3>💼 Work Experience</h3>
                        </div>

                        {/* Data Annotation Interest Card - From Profile Wizard */}
                        {profile && profile.has_data_annotation_experience !== null && (
                            <div className="annotation-interest-card">
                                <div className="annotation-header">
                                    <span className="annotation-icon">🤖</span>
                                    <div>
                                        <h4>Data Annotation Experience</h4>
                                        <span className={`annotation-badge ${profile?.has_data_annotation_experience ? 'yes' : 'no'}`}>
                                            {profile?.has_data_annotation_experience ? 'Experienced' : 'New to this field'}
                                        </span>
                                    </div>
                                </div>
                                {profile?.why_annotation && (
                                    <p className="annotation-reason">
                                        <strong>Interest:</strong> {profile?.why_annotation}
                                    </p>
                                )}
                            </div>
                        )}

                        {profile?.work_experience && profile.work_experience.length > 0 ? (
                            <div className="entries-list">
                                {profile.work_experience.map(exp => (
                                    <div key={exp.id} className="entry-card">
                                        <div className="entry-header">
                                            <div>
                                                <h4 className="entry-title">{exp.role}</h4>
                                                <p className="entry-subtitle">{exp.company}</p>
                                            </div>
                                            {exp.is_current && (
                                                <span className="entry-badge">Current</span>
                                            )}
                                        </div>
                                        <div className="entry-meta">
                                            <span className="entry-date">
                                                📅 {exp.start_date} - {exp.is_current ? 'Present' : exp.end_date}
                                            </span>
                                            {exp.city && (
                                                <span>📍 {exp.city}{exp.country && `, ${exp.country}`}</span>
                                            )}
                                        </div>
                                        {exp.description && (
                                            <div className="entry-description">
                                                <ul className="bullet-list">
                                                    {parseBulletPoints(exp.description).map((bullet, idx) => (
                                                        <li key={idx}>{bullet}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="fresher-card">
                                <div className="fresher-icon">🎓</div>
                                <h4>Fresh Graduate</h4>
                                <p>No professional work experience yet. Ready to start your career journey!</p>
                                <div className="fresher-tips">
                                    <span>Your academic background and projects showcase your potential.</span>
                                </div>
                            </div>
                        )}
                    </div>
                );

            case 'resume':
                return (
                    <div className="tab-panel">
                        <div className="tab-panel-header">
                            <h3>📄 Resume</h3>
                        </div>

                        {error && (
                            <div className="error-banner">
                                <span>⚠️ {error}</span>
                                <button onClick={() => setError(null)}>×</button>
                            </div>
                        )}

                        <div className="upload-container">
                            <div
                                className={`upload-dropzone ${dragActive ? 'drag-active' : ''} ${uploading ? 'uploading' : ''}`}
                                onDragEnter={handleDrag}
                                onDragLeave={handleDrag}
                                onDragOver={handleDrag}
                                onDrop={handleDrop}
                            >
                                <input
                                    type="file"
                                    id="resume-upload"
                                    accept=".pdf"
                                    onChange={handleFileInput}
                                    disabled={uploading}
                                    style={{ display: 'none' }}
                                />
                                <label htmlFor="resume-upload" style={{ cursor: 'pointer', display: 'block' }}>
                                    {uploading ? (
                                        <div className="upload-progress-container">
                                            <div className="progress-bar-track">
                                                <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                                            </div>
                                            <p className="progress-text">🤖 AI is parsing your resume... {uploadProgress}%</p>
                                        </div>
                                    ) : (
                                        <>
                                            <div className="upload-icon">📄</div>
                                            <h4 className="upload-title">
                                                {profile?.resume_filename ? 'Update Your Resume' : 'Upload Your Resume'}
                                            </h4>
                                            <p className="upload-subtitle">
                                                Drag & drop your PDF here or click to browse
                                            </p>
                                            {profile?.resume_filename && (
                                                <span className="current-file-badge">
                                                    ✓ {profile.resume_filename}
                                                </span>
                                            )}
                                        </>
                                    )}
                                </label>
                            </div>
                        </div>

                        {profile?.professional_summary && (
                            <div className="summary-card">
                                <h4>✨ Professional Summary</h4>
                                <p>{profile.professional_summary}</p>
                            </div>
                        )}
                    </div>
                );

            case 'skills':
                return (
                    <div className="tab-panel">
                        <div className="tab-panel-header">
                            <h3>⚡ Skills & Projects</h3>
                        </div>

                        {/* Skills Section - Always show */}
                        <div className="skills-section">
                            <h4>Technical Skills</h4>
                            <div className="skills-grid">
                                {/* Data Annotation skill from wizard - Priority display */}
                                {profile?.has_data_annotation_experience && (
                                    <span className="skill-chip annotation-skill">
                                        🤖 Data Annotation
                                    </span>
                                )}
                                {profile?.skills && profile.skills.length > 0 ? (
                                    profile.skills.map(skill => (
                                        <span
                                            key={skill.id}
                                            className={`skill-chip ${skill.category || 'other'}`}
                                        >
                                            {skill.display_name}
                                        </span>
                                    ))
                                ) : (
                                    !profile?.has_data_annotation_experience && (
                                        <span className="no-skills-text">Upload resume to extract skills</span>
                                    )
                                )}
                            </div>
                        </div>

                        {profile?.projects && profile.projects.length > 0 ? (
                            <div className="skills-section">
                                <h4>Projects</h4>
                                <div className="projects-grid">
                                    {profile.projects.map(proj => (
                                        <div key={proj.id} className="project-card">
                                            <div className="project-card-header">
                                                <h5 className="project-card-title">{proj.name}</h5>
                                                {proj.url && (
                                                    <a href={proj.url} target="_blank" rel="noopener noreferrer" className="project-link">
                                                        🔗
                                                    </a>
                                                )}
                                            </div>
                                            {proj.description && (
                                                <div className="project-card-description">
                                                    <ul className="bullet-list">
                                                        {parseBulletPoints(proj.description).map((bullet, idx) => (
                                                            <li key={idx}>{bullet}</li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                            {proj.technologies.length > 0 && (
                                                <div className="project-tech-tags">
                                                    {proj.technologies.map((tech, i) => (
                                                        <span key={i} className="tech-tag">{tech}</span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            !profile?.skills?.length && (
                                <div className="empty-state">
                                    <span className="empty-state-icon">🛠️</span>
                                    <h4 className="empty-state-title">No Skills or Projects</h4>
                                    <p className="empty-state-text">Upload your resume to automatically extract your skills and projects.</p>
                                </div>
                            )
                        )}
                    </div>
                );

            case 'settings':
                return (
                    <div className="tab-panel">
                        <div className="tab-panel-header">
                            <h3>⚙️ Account Settings</h3>
                        </div>
                        <div className="empty-state">
                            <span className="empty-state-icon">🔧</span>
                            <h4 className="empty-state-title">Settings Coming Soon</h4>
                            <p className="empty-state-text">Account settings and preferences will be available here.</p>
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="profile-dashboard">
            <div className="profile-dashboard-header">
                <h1>My Profile</h1>
                <p className="subtitle">Manage your professional profile and resume</p>
            </div>

            <div className="profile-layout">
                {/* Left Sidebar - Profile Card (Fixed Template) */}
                <div className="profile-card">
                    <div className="profile-card-banner"></div>
                    <div className="profile-card-body">
                        <div className="profile-avatar-wrapper">
                            <img
                                src={user?.avatar_url || getAvatarUrl(user?.name)}
                                alt="Profile"
                                className="profile-avatar"
                            />
                        </div>
                        <h2 className="profile-name">{user?.name || 'User'}</h2>
                        <p className="profile-email">{user?.email || '-'}</p>

                        {/* Role Badge - Fixed: Show role or Fresher */}
                        <span className="profile-role-badge">
                            {profile?.current_role || (profile?.years_of_experience && profile.years_of_experience > 0
                                ? 'Professional'
                                : 'Fresher')}
                        </span>

                        {/* Fixed Template Info Tags - Always show structure */}
                        <div className="profile-info-tags">
                            {/* Education - Always show */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">🎓</span>
                                <span className="tag-text">{user?.degree || 'Not specified'}</span>
                            </span>

                            {/* Branch - Always show */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">📚</span>
                                <span className="tag-text">{user?.branch || 'Not specified'}</span>
                            </span>

                            {/* Batch - Always show */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">📅</span>
                                <span className="tag-text">Batch {user?.batch || '-'}</span>
                            </span>

                            {/* Company - Show if has experience, else show Fresher note */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">🏢</span>
                                <span className="tag-text">
                                    {profile?.current_company || (profile?.years_of_experience && profile.years_of_experience > 0
                                        ? 'Not specified'
                                        : 'Fresher - No company yet')}
                                </span>
                            </span>

                            {/* Experience - Always show */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">⏳</span>
                                <span className="tag-text">
                                    {profile?.years_of_experience && profile.years_of_experience > 0
                                        ? `${profile.years_of_experience} years exp`
                                        : 'Fresher'}
                                </span>
                            </span>

                            {/* Data Annotation Interest - Show if answered */}
                            {profile && profile.has_data_annotation_experience !== null && (
                                <span className={`profile-info-tag ${profile?.has_data_annotation_experience ? 'highlight' : ''}`}>
                                    <span className="tag-icon">🤖</span>
                                    <span className="tag-text">
                                        {profile?.has_data_annotation_experience
                                            ? 'Data Annotation Exp.'
                                            : 'New to Data Annotation'}
                                    </span>
                                </span>
                            )}
                        </div>

                        {/* Profile Links - Always show section */}
                        <div className="profile-links">
                            {profile?.linkedin_url ? (
                                <a
                                    href={profile.linkedin_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="profile-link-btn"
                                >
                                    💼 LinkedIn
                                </a>
                            ) : (
                                <span className="profile-link-btn disabled">💼 LinkedIn</span>
                            )}
                            {profile?.github_url ? (
                                <a
                                    href={profile.github_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="profile-link-btn"
                                >
                                    🐙 GitHub
                                </a>
                            ) : (
                                <span className="profile-link-btn disabled">🐙 GitHub</span>
                            )}
                        </div>
                    </div>
                </div>

                {/* Right Content Area */}
                <div className="profile-content">
                    {/* Tab Navigation */}
                    <div className="profile-tabs-container">
                        <div className="profile-tabs">
                            {tabs.map(tab => (
                                <button
                                    key={tab.id}
                                    className={`profile-tab ${activeTab === tab.id ? 'active' : ''}`}
                                    onClick={() => setActiveTab(tab.id)}
                                >
                                    <span className="tab-icon">{tab.icon}</span>
                                    {tab.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Tab Content */}
                    {renderTabContent()}
                </div>
            </div>
        </div>
    );
}

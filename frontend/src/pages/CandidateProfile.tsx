import { useState, useEffect, useCallback } from 'react';
import { profileApi } from '../services/api';
import type { User } from '../types';
import './CandidateProfile.css';

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

interface Profile {
    id: number;
    user_id: number;
    resume_filename: string | null;
    resume_parsed_at: string | null;
    professional_summary: string | null;
    linkedin_url: string | null;
    github_url: string | null;
    portfolio_url: string | null;
    location: string | null;
    years_of_experience: number | null;
    current_role: string | null;
    current_company: string | null;
    leetcode_username: string | null;
    codechef_username: string | null;
    codeforces_username: string | null;
    education: Education[];
    work_experience: WorkExperience[];
    projects: Project[];
    skills: Skill[];
    certifications: { id: number; title: string; issuer: string | null; year: number | null }[];
    awards: { id: number; title: string; issuer: string | null; year: number | null }[];
    languages: { id: number; language: string; proficiency: string | null }[];
}

export default function CandidateProfile({ user: _user }: ProfileProps) {
    const [profile, setProfile] = useState<Profile | null>(null);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [dragActive, setDragActive] = useState(false);
    const [activeTab, setActiveTab] = useState<'overview' | 'education' | 'experience' | 'skills' | 'projects'>('overview');

    // Fetch profile on mount
    useEffect(() => {
        fetchProfile();
    }, []);

    const fetchProfile = async () => {
        try {
            setLoading(true);
            const data = await profileApi.getMyProfile();
            setProfile(data);
        } catch (err: any) {
            if (err.response?.status !== 404) {
                setError('Failed to load profile');
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

            // Simulate progress
            const progressInterval = setInterval(() => {
                setUploadProgress(prev => Math.min(prev + 10, 90));
            }, 500);

            const data = await profileApi.uploadResume(file);

            clearInterval(progressInterval);
            setUploadProgress(100);
            setProfile(data);

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

    if (loading) {
        return (
            <div className="profile-page">
                <div className="loading-container">
                    <div className="spinner"></div>
                    <p>Loading profile...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="profile-page">
            <div className="profile-header">
                <h1>My Profile</h1>
                <p className="subtitle">
                    {profile ? 'View and manage your professional profile' : 'Upload your resume to get started'}
                </p>
            </div>

            {error && (
                <div className="error-banner">
                    <span>⚠️ {error}</span>
                    <button onClick={() => setError(null)}>×</button>
                </div>
            )}

            {/* Resume Upload Section */}
            <div className="upload-section">
                <div
                    className={`upload-zone ${dragActive ? 'drag-active' : ''} ${uploading ? 'uploading' : ''}`}
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
                        className="file-input"
                    />
                    <label htmlFor="resume-upload" className="upload-label">
                        {uploading ? (
                            <div className="upload-progress">
                                <div className="progress-bar">
                                    <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
                                </div>
                                <p>Parsing resume with AI... {uploadProgress}%</p>
                            </div>
                        ) : (
                            <>
                                <div className="upload-icon">📄</div>
                                <h3>{profile?.resume_filename ? 'Update Resume' : 'Upload Resume'}</h3>
                                <p>Drag & drop your PDF here or click to browse</p>
                                {profile?.resume_filename && (
                                    <p className="current-file">Current: {profile.resume_filename}</p>
                                )}
                            </>
                        )}
                    </label>
                </div>
            </div>

            {/* Profile Content */}
            {profile && (
                <div className="profile-content">
                    {/* Tabs */}
                    <div className="profile-tabs">
                        <button
                            className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
                            onClick={() => setActiveTab('overview')}
                        >
                            Overview
                        </button>
                        <button
                            className={`tab ${activeTab === 'education' ? 'active' : ''}`}
                            onClick={() => setActiveTab('education')}
                        >
                            Education ({profile.education.length})
                        </button>
                        <button
                            className={`tab ${activeTab === 'experience' ? 'active' : ''}`}
                            onClick={() => setActiveTab('experience')}
                        >
                            Experience ({profile.work_experience.length})
                        </button>
                        <button
                            className={`tab ${activeTab === 'skills' ? 'active' : ''}`}
                            onClick={() => setActiveTab('skills')}
                        >
                            Skills ({profile.skills.length})
                        </button>
                        <button
                            className={`tab ${activeTab === 'projects' ? 'active' : ''}`}
                            onClick={() => setActiveTab('projects')}
                        >
                            Projects ({profile.projects.length})
                        </button>
                    </div>

                    {/* Tab Content */}
                    <div className="tab-content">
                        {/* Overview Tab */}
                        {activeTab === 'overview' && (
                            <div className="overview-tab">
                                <div className="summary-card">
                                    <h3>Professional Summary</h3>
                                    <p>{profile.professional_summary || 'No summary available'}</p>
                                </div>

                                <div className="info-grid">
                                    <div className="info-card">
                                        <h4>Current Position</h4>
                                        <p className="value">{profile.current_role || 'Not specified'}</p>
                                        <p className="label">{profile.current_company || ''}</p>
                                    </div>
                                    <div className="info-card">
                                        <h4>Experience</h4>
                                        <p className="value">{profile.years_of_experience ? `${profile.years_of_experience} years` : 'Not specified'}</p>
                                    </div>
                                    <div className="info-card">
                                        <h4>Location</h4>
                                        <p className="value">{profile.location || 'Not specified'}</p>
                                    </div>
                                </div>

                                {/* Links */}
                                <div className="links-section">
                                    <h4>Profiles & Links</h4>
                                    <div className="links-grid">
                                        {profile.linkedin_url && (
                                            <a href={profile.linkedin_url} target="_blank" rel="noopener noreferrer" className="link-item">
                                                <span className="link-icon">💼</span> LinkedIn
                                            </a>
                                        )}
                                        {profile.github_url && (
                                            <a href={profile.github_url} target="_blank" rel="noopener noreferrer" className="link-item">
                                                <span className="link-icon">🐙</span> GitHub
                                            </a>
                                        )}
                                        {profile.portfolio_url && (
                                            <a href={profile.portfolio_url} target="_blank" rel="noopener noreferrer" className="link-item">
                                                <span className="link-icon">🌐</span> Portfolio
                                            </a>
                                        )}
                                        {profile.leetcode_username && (
                                            <a href={`https://leetcode.com/${profile.leetcode_username}`} target="_blank" rel="noopener noreferrer" className="link-item">
                                                <span className="link-icon">🧩</span> LeetCode
                                            </a>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Education Tab */}
                        {activeTab === 'education' && (
                            <div className="education-tab">
                                {profile.education.length === 0 ? (
                                    <p className="empty-state">No education entries found</p>
                                ) : (
                                    profile.education.map(edu => (
                                        <div key={edu.id} className="entry-card">
                                            <h4>{edu.school}</h4>
                                            <p className="degree">
                                                {edu.degree}
                                                {edu.field_of_study && !edu.degree?.toLowerCase().includes(edu.field_of_study.toLowerCase()) && ` in ${edu.field_of_study}`}
                                            </p>
                                            <p className="dates">
                                                {edu.start_year} - {edu.end_year || 'Present'}
                                                {edu.gpa && <span className="gpa">GPA: {edu.gpa}</span>}
                                            </p>
                                        </div>
                                    ))
                                )}
                            </div>
                        )}

                        {/* Experience Tab */}
                        {activeTab === 'experience' && (
                            <div className="experience-tab">
                                {profile.work_experience.length === 0 ? (
                                    <p className="empty-state">No work experience found</p>
                                ) : (
                                    profile.work_experience.map(exp => (
                                        <div key={exp.id} className="entry-card">
                                            <h4>{exp.role}</h4>
                                            <p className="company">{exp.company} {exp.city && `• ${exp.city}`}</p>
                                            <p className="dates">
                                                {exp.start_date} - {exp.is_current ? 'Present' : exp.end_date}
                                            </p>
                                            {exp.description && <p className="description">{exp.description}</p>}
                                        </div>
                                    ))
                                )}
                            </div>
                        )}

                        {/* Skills Tab */}
                        {activeTab === 'skills' && (
                            <div className="skills-tab">
                                {profile.skills.length === 0 ? (
                                    <p className="empty-state">No skills found</p>
                                ) : (
                                    <div className="skills-grid">
                                        {profile.skills.map(skill => (
                                            <span key={skill.id} className={`skill-tag ${skill.category || 'other'}`}>
                                                {skill.display_name}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Projects Tab */}
                        {activeTab === 'projects' && (
                            <div className="projects-tab">
                                {profile.projects.length === 0 ? (
                                    <p className="empty-state">No projects found</p>
                                ) : (
                                    profile.projects.map(proj => (
                                        <div key={proj.id} className="entry-card">
                                            <h4>
                                                {proj.name}
                                                {proj.url && (
                                                    <a href={proj.url} target="_blank" rel="noopener noreferrer" className="project-link">🔗</a>
                                                )}
                                            </h4>
                                            {proj.description && <p className="description">{proj.description}</p>}
                                            {proj.technologies.length > 0 && (
                                                <div className="tech-tags">
                                                    {proj.technologies.map((tech, i) => (
                                                        <span key={i} className="tech-tag">{tech}</span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    ))
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* No Profile State */}
            {!profile && !loading && (
                <div className="no-profile">
                    <div className="empty-icon">📋</div>
                    <h3>No Profile Yet</h3>
                    <p>Upload your resume above to automatically create your profile with AI</p>
                </div>
            )}
        </div>
    );
}

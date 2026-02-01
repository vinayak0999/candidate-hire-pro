import { useState, useEffect, useCallback } from 'react';
import { profileApi } from '../services/api';
import type { User } from '../types';
import './Profile.css';
import profileBanner from '../assets/banner.jpg';

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

    // Inline Edit State for Tab Content
    const [editMode, setEditMode] = useState<Record<string, boolean>>({});
    const [editValues, setEditValues] = useState<Record<string, string>>({});
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);

    // Modal/Form State for CRUD operations
    const [showAddModal, setShowAddModal] = useState<string | null>(null); // 'education' | 'experience' | 'project' | 'skill'
    const [editingItem, setEditingItem] = useState<{ type: string; id: number; data: Record<string, unknown> } | null>(null);
    const [formData, setFormData] = useState<Record<string, unknown>>({});
    const [formSaving, setFormSaving] = useState(false);

    // Computed values from profile data
    const latestEducation = profile?.education?.[0] || null;
    const latestExperience = profile?.work_experience?.[0] || null;
    const hasWorkExperience = (profile?.work_experience?.length || 0) > 0;

    // Toggle edit mode for a field
    const toggleEdit = useCallback((field: string) => {
        setEditMode(prev => ({ ...prev, [field]: !prev[field] }));
        // Initialize edit value with current profile value
        if (!editMode[field] && profile) {
            const currentValue = (profile as unknown as Record<string, unknown>)[field];
            setEditValues(prev => ({
                ...prev,
                [field]: currentValue !== null && currentValue !== undefined ? String(currentValue) : ''
            }));
        }
    }, [editMode, profile]);

    // Save a single field
    const saveField = useCallback(async (field: string) => {
        if (!profile) return;

        setSaving(true);
        try {
            const updateData: Record<string, string | number | undefined> = {};
            const value = editValues[field];

            // Handle number fields
            if (field === 'years_of_experience') {
                updateData[field] = value ? parseFloat(value) : undefined;
            } else {
                updateData[field] = value || undefined;
            }

            const updatedProfile = await profileApi.updateProfile(updateData);
            setProfile(updatedProfile);

            // Exit edit mode
            setEditMode(prev => ({ ...prev, [field]: false }));

            // Show success message
            setSaveMessage('✓ Saved successfully!');
            setTimeout(() => setSaveMessage(null), 2000);
        } catch (err: any) {
            console.error('Failed to save:', err);
            setError(err.response?.data?.detail || 'Failed to save changes');
        } finally {
            setSaving(false);
        }
    }, [profile, editValues]);

    // Cancel editing
    const cancelEdit = useCallback((field: string) => {
        setEditMode(prev => ({ ...prev, [field]: false }));
        setEditValues(prev => {
            const updated = { ...prev };
            delete updated[field];
            return updated;
        });
    }, []);

    // Update edit value
    const updateEditValue = useCallback((field: string, value: string) => {
        setEditValues(prev => ({ ...prev, [field]: value }));
    }, []);

    // Open add modal for a specific type
    const openAddModal = useCallback((type: string) => {
        setShowAddModal(type);
        setFormData({});
        setEditingItem(null);
    }, []);

    // Open edit modal for a specific item
    const openEditModal = useCallback((type: string, id: number, data: Record<string, unknown>) => {
        setShowAddModal(type);
        setEditingItem({ type, id, data });
        setFormData(data);
    }, []);

    // Close modal
    const closeModal = useCallback(() => {
        setShowAddModal(null);
        setEditingItem(null);
        setFormData({});
    }, []);

    // Update form data
    const updateFormField = useCallback((field: string, value: unknown) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    }, []);

    // Handle form submission for add/edit
    const handleFormSubmit = useCallback(async () => {
        if (!showAddModal) return;

        setFormSaving(true);
        try {
            let result;

            if (editingItem) {
                // Update existing
                switch (showAddModal) {
                    case 'education':
                        result = await profileApi.updateEducation(editingItem.id, formData as any);
                        break;
                    case 'experience':
                        result = await profileApi.updateExperience(editingItem.id, formData as any);
                        break;
                    case 'project':
                        result = await profileApi.updateProject(editingItem.id, formData as any);
                        break;
                }
            } else {
                // Add new
                switch (showAddModal) {
                    case 'education':
                        result = await profileApi.addEducation(formData as any);
                        break;
                    case 'experience':
                        result = await profileApi.addExperience(formData as any);
                        break;
                    case 'project':
                        result = await profileApi.addProject(formData as any);
                        break;
                    case 'skill':
                        result = await profileApi.addSkill(formData as any);
                        break;
                }
            }

            if (result) {
                setProfile(result);
                setSaveMessage('✓ Saved successfully!');
                setTimeout(() => setSaveMessage(null), 2000);
            }
            closeModal();
        } catch (err: any) {
            console.error('Failed to save:', err);
            setError(err.response?.data?.detail || 'Failed to save');
        } finally {
            setFormSaving(false);
        }
    }, [showAddModal, editingItem, formData, closeModal]);

    // Delete handlers
    const handleDeleteEducation = useCallback(async (id: number) => {
        if (!confirm('Delete this education entry?')) return;
        try {
            await profileApi.deleteEducation(id);
            fetchProfile();
            setSaveMessage('✓ Deleted successfully!');
            setTimeout(() => setSaveMessage(null), 2000);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete');
        }
    }, []);

    const handleDeleteExperience = useCallback(async (id: number) => {
        if (!confirm('Delete this experience entry?')) return;
        try {
            await profileApi.deleteExperience(id);
            fetchProfile();
            setSaveMessage('✓ Deleted successfully!');
            setTimeout(() => setSaveMessage(null), 2000);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete');
        }
    }, []);

    const handleDeleteProject = useCallback(async (id: number) => {
        if (!confirm('Delete this project?')) return;
        try {
            await profileApi.deleteProject(id);
            fetchProfile();
            setSaveMessage('✓ Deleted successfully!');
            setTimeout(() => setSaveMessage(null), 2000);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete');
        }
    }, []);

    const handleRemoveSkill = useCallback(async (id: number) => {
        if (!confirm('Remove this skill?')) return;
        try {
            await profileApi.removeSkill(id);
            fetchProfile();
            setSaveMessage('✓ Removed successfully!');
            setTimeout(() => setSaveMessage(null), 2000);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to remove');
        }
    }, []);

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

            // Upload file - returns immediately, parses in background
            await profileApi.uploadResume(file);
            setUploadProgress(30);

            // Poll for parsing completion (up to 60 seconds)
            const maxAttempts = 30;
            let attempts = 0;
            let parsingComplete = false;

            while (attempts < maxAttempts && !parsingComplete) {
                await new Promise(resolve => setTimeout(resolve, 2000)); // Wait 2 seconds
                attempts++;
                setUploadProgress(30 + Math.min(attempts * 2, 60)); // Progress 30-90%

                try {
                    // Check parsing status
                    const status = await profileApi.getResumeStatus();
                    console.log('Resume parsing status:', status);

                    if (status.status === 'completed') {
                        parsingComplete = true;
                    } else if (status.status === 'failed') {
                        throw new Error(status.error_message || 'Resume parsing failed');
                    } else if (status.status === 'none') {
                        // No job tracking - just wait and refetch profile
                        parsingComplete = true;
                    }
                    // 'pending' or 'processing' - keep polling
                } catch (statusErr: any) {
                    // If status check fails, try refetching profile directly
                    console.log('Status check failed, trying profile refetch');
                    parsingComplete = true;
                }
            }

            setUploadProgress(100);

            // Refetch profile to get parsed data
            try {
                const data = await profileApi.getMyProfile();
                setProfile(data);
            } catch (e) {
                console.error('Failed to refetch profile:', e);
            }

            setTimeout(() => setUploadProgress(0), 1000);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to upload resume');
            setUploadProgress(0);
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
                            <button className="add-entry-btn" onClick={() => openAddModal('education')}>
                                + Add Education
                            </button>
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
                                            <div className="entry-actions">
                                                {edu.gpa && (
                                                    <span className="entry-badge">GPA: {edu.gpa}</span>
                                                )}
                                                <button
                                                    className="entry-action-btn edit"
                                                    onClick={() => openEditModal('education', edu.id, {
                                                        school: edu.school,
                                                        degree: edu.degree,
                                                        field_of_study: edu.field_of_study,
                                                        start_year: edu.start_year,
                                                        end_year: edu.end_year,
                                                        gpa: edu.gpa
                                                    })}
                                                    title="Edit"
                                                >
                                                    ✏️
                                                </button>
                                                <button
                                                    className="entry-action-btn delete"
                                                    onClick={() => handleDeleteEducation(edu.id)}
                                                    title="Delete"
                                                >
                                                    🗑️
                                                </button>
                                            </div>
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
                                <p className="empty-state-text">Upload your resume or click "Add Education" to add your education history.</p>
                            </div>
                        )}
                    </div>
                );

            case 'experience':
                return (
                    <div className="tab-panel">
                        <div className="tab-panel-header">
                            <h3>💼 Work Experience</h3>
                            <button className="add-entry-btn" onClick={() => openAddModal('experience')}>
                                + Add Experience
                            </button>
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
                                            <div className="entry-actions">
                                                {exp.is_current && (
                                                    <span className="entry-badge">Current</span>
                                                )}
                                                <button
                                                    className="entry-action-btn edit"
                                                    onClick={() => openEditModal('experience', exp.id, {
                                                        company: exp.company,
                                                        role: exp.role,
                                                        city: exp.city,
                                                        country: exp.country,
                                                        start_date: exp.start_date,
                                                        end_date: exp.end_date,
                                                        is_current: exp.is_current,
                                                        description: exp.description
                                                    })}
                                                    title="Edit"
                                                >
                                                    ✏️
                                                </button>
                                                <button
                                                    className="entry-action-btn delete"
                                                    onClick={() => handleDeleteExperience(exp.id)}
                                                    title="Delete"
                                                >
                                                    🗑️
                                                </button>
                                            </div>
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
                                <p>No professional work experience yet. Click "Add Experience" to add your work history.</p>
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

                        {/* Professional Summary - Editable */}
                        <div className="summary-card editable-section">
                            <div className="section-header">
                                <h4>✨ Professional Summary</h4>
                                {!editMode['professional_summary'] ? (
                                    <button
                                        className="edit-section-btn"
                                        onClick={() => toggleEdit('professional_summary')}
                                    >
                                        ✏️ Edit
                                    </button>
                                ) : (
                                    <div className="edit-actions">
                                        <button
                                            className="save-btn"
                                            onClick={() => saveField('professional_summary')}
                                            disabled={saving}
                                        >
                                            {saving ? '...' : '✓ Save'}
                                        </button>
                                        <button
                                            className="cancel-btn"
                                            onClick={() => cancelEdit('professional_summary')}
                                            disabled={saving}
                                        >
                                            ✕ Cancel
                                        </button>
                                    </div>
                                )}
                            </div>
                            {editMode['professional_summary'] ? (
                                <textarea
                                    className="edit-textarea"
                                    value={editValues['professional_summary'] || ''}
                                    onChange={(e) => updateEditValue('professional_summary', e.target.value)}
                                    placeholder="Write a brief professional summary about yourself..."
                                    rows={5}
                                    autoFocus
                                />
                            ) : (
                                <p>{profile?.professional_summary || 'No summary yet. Click Edit to add one.'}</p>
                            )}
                            {saveMessage && <span className="save-message">{saveMessage}</span>}
                        </div>
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
                            <div className="section-header">
                                <h4>Technical Skills</h4>
                                <button className="add-entry-btn small" onClick={() => openAddModal('skill')}>
                                    + Add Skill
                                </button>
                            </div>
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
                                            className={`skill-chip with-remove ${skill.category || 'other'}`}
                                        >
                                            {skill.display_name}
                                            <button
                                                className="skill-remove-btn"
                                                onClick={() => handleRemoveSkill(skill.id)}
                                                title="Remove skill"
                                            >
                                                ×
                                            </button>
                                        </span>
                                    ))
                                ) : (
                                    !profile?.has_data_annotation_experience && (
                                        <span className="no-skills-text">Upload resume or add skills manually</span>
                                    )
                                )}
                            </div>
                        </div>

                        {/* Projects Section */}
                        <div className="skills-section">
                            <div className="section-header">
                                <h4>Projects</h4>
                                <button className="add-entry-btn small" onClick={() => openAddModal('project')}>
                                    + Add Project
                                </button>
                            </div>
                            {profile?.projects && profile.projects.length > 0 ? (
                                <div className="projects-grid">
                                    {profile.projects.map(proj => (
                                        <div key={proj.id} className="project-card">
                                            <div className="project-card-header">
                                                <h5 className="project-card-title">{proj.name}</h5>
                                                <div className="project-actions">
                                                    {proj.url && (
                                                        <a href={proj.url} target="_blank" rel="noopener noreferrer" className="project-link">
                                                            🔗
                                                        </a>
                                                    )}
                                                    <button
                                                        className="entry-action-btn edit"
                                                        onClick={() => openEditModal('project', proj.id, {
                                                            name: proj.name,
                                                            description: proj.description,
                                                            technologies: proj.technologies,
                                                            start_year: proj.start_year,
                                                            end_year: proj.end_year,
                                                            url: proj.url
                                                        })}
                                                        title="Edit"
                                                    >
                                                        ✏️
                                                    </button>
                                                    <button
                                                        className="entry-action-btn delete"
                                                        onClick={() => handleDeleteProject(proj.id)}
                                                        title="Delete"
                                                    >
                                                        🗑️
                                                    </button>
                                                </div>
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
                            ) : (
                                <div className="empty-state small">
                                    <span className="empty-state-icon">📁</span>
                                    <p className="empty-state-text">No projects yet. Click "Add Project" to showcase your work.</p>
                                </div>
                            )}
                        </div>
                    </div>
                );

            case 'settings':
                return (
                    <div className="tab-panel">
                        <div className="tab-panel-header">
                            <h3>⚙️ Profile Settings</h3>
                        </div>

                        {saveMessage && <div className="success-banner">{saveMessage}</div>}

                        {/* Current Position Section */}
                        <div className="settings-section">
                            <h4>💼 Current Position</h4>
                            <div className="settings-grid">
                                <div className="setting-field">
                                    <label>Current Role</label>
                                    {editMode['current_role'] ? (
                                        <div className="edit-field-wrapper">
                                            <input
                                                type="text"
                                                value={editValues['current_role'] || ''}
                                                onChange={(e) => updateEditValue('current_role', e.target.value)}
                                                placeholder="e.g., Software Engineer"
                                                className="edit-input"
                                                autoFocus
                                            />
                                            <div className="field-actions">
                                                <button className="save-btn" onClick={() => saveField('current_role')} disabled={saving}>
                                                    {saving ? '...' : '✓'}
                                                </button>
                                                <button className="cancel-btn" onClick={() => cancelEdit('current_role')}>✕</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="display-field" onClick={() => toggleEdit('current_role')}>
                                            <span>{profile?.current_role || 'Not specified'}</span>
                                            <button className="edit-pencil">✏️</button>
                                        </div>
                                    )}
                                </div>

                                <div className="setting-field">
                                    <label>Current Company</label>
                                    {editMode['current_company'] ? (
                                        <div className="edit-field-wrapper">
                                            <input
                                                type="text"
                                                value={editValues['current_company'] || ''}
                                                onChange={(e) => updateEditValue('current_company', e.target.value)}
                                                placeholder="e.g., Google"
                                                className="edit-input"
                                                autoFocus
                                            />
                                            <div className="field-actions">
                                                <button className="save-btn" onClick={() => saveField('current_company')} disabled={saving}>
                                                    {saving ? '...' : '✓'}
                                                </button>
                                                <button className="cancel-btn" onClick={() => cancelEdit('current_company')}>✕</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="display-field" onClick={() => toggleEdit('current_company')}>
                                            <span>{profile?.current_company || 'Not specified'}</span>
                                            <button className="edit-pencil">✏️</button>
                                        </div>
                                    )}
                                </div>

                                <div className="setting-field">
                                    <label>Years of Experience</label>
                                    {editMode['years_of_experience'] ? (
                                        <div className="edit-field-wrapper">
                                            <input
                                                type="number"
                                                step="0.5"
                                                min="0"
                                                value={editValues['years_of_experience'] || ''}
                                                onChange={(e) => updateEditValue('years_of_experience', e.target.value)}
                                                placeholder="e.g., 3.5"
                                                className="edit-input"
                                                autoFocus
                                            />
                                            <div className="field-actions">
                                                <button className="save-btn" onClick={() => saveField('years_of_experience')} disabled={saving}>
                                                    {saving ? '...' : '✓'}
                                                </button>
                                                <button className="cancel-btn" onClick={() => cancelEdit('years_of_experience')}>✕</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="display-field" onClick={() => toggleEdit('years_of_experience')}>
                                            <span>{profile?.years_of_experience ? `${profile.years_of_experience} years` : 'Not specified'}</span>
                                            <button className="edit-pencil">✏️</button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Social Links Section */}
                        <div className="settings-section">
                            <h4>🔗 Social Links</h4>
                            <div className="settings-grid">
                                <div className="setting-field">
                                    <label>LinkedIn URL</label>
                                    {editMode['linkedin_url'] ? (
                                        <div className="edit-field-wrapper">
                                            <input
                                                type="url"
                                                value={editValues['linkedin_url'] || ''}
                                                onChange={(e) => updateEditValue('linkedin_url', e.target.value)}
                                                placeholder="https://linkedin.com/in/yourname"
                                                className="edit-input"
                                                autoFocus
                                            />
                                            <div className="field-actions">
                                                <button className="save-btn" onClick={() => saveField('linkedin_url')} disabled={saving}>
                                                    {saving ? '...' : '✓'}
                                                </button>
                                                <button className="cancel-btn" onClick={() => cancelEdit('linkedin_url')}>✕</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="display-field" onClick={() => toggleEdit('linkedin_url')}>
                                            <span>{profile?.linkedin_url || 'Not specified'}</span>
                                            <button className="edit-pencil">✏️</button>
                                        </div>
                                    )}
                                </div>

                                <div className="setting-field">
                                    <label>GitHub URL</label>
                                    {editMode['github_url'] ? (
                                        <div className="edit-field-wrapper">
                                            <input
                                                type="url"
                                                value={editValues['github_url'] || ''}
                                                onChange={(e) => updateEditValue('github_url', e.target.value)}
                                                placeholder="https://github.com/username"
                                                className="edit-input"
                                                autoFocus
                                            />
                                            <div className="field-actions">
                                                <button className="save-btn" onClick={() => saveField('github_url')} disabled={saving}>
                                                    {saving ? '...' : '✓'}
                                                </button>
                                                <button className="cancel-btn" onClick={() => cancelEdit('github_url')}>✕</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="display-field" onClick={() => toggleEdit('github_url')}>
                                            <span>{profile?.github_url || 'Not specified'}</span>
                                            <button className="edit-pencil">✏️</button>
                                        </div>
                                    )}
                                </div>
                            </div>
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
                    <div className="profile-card-banner" style={{ backgroundImage: `url(${profileBanner})` }}></div>
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

                        {/* Role Badge - Show current role, latest job role, or Fresher */}
                        <span className="profile-role-badge">
                            {profile?.current_role || latestExperience?.role || (hasWorkExperience
                                ? 'Professional'
                                : 'Fresher')}
                        </span>

                        {/* Fixed Template Info Tags - Data from resume parsing */}
                        <div className="profile-info-tags">
                            {/* Degree - From resume education OR user field */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">🎓</span>
                                <span className="tag-text">
                                    {latestEducation?.degree || user?.degree || 'Not specified'}
                                </span>
                            </span>

                            {/* Branch/Field - From resume education OR user field */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">📚</span>
                                <span className="tag-text">
                                    {latestEducation?.field_of_study || user?.branch || 'Not specified'}
                                </span>
                            </span>

                            {/* Batch - From resume education end_year OR user field */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">📅</span>
                                <span className="tag-text">
                                    Batch {latestEducation?.end_year || user?.batch || '-'}
                                </span>
                            </span>

                            {/* Company - From profile or latest experience */}
                            <span className="profile-info-tag">
                                <span className="tag-icon">🏢</span>
                                <span className="tag-text">
                                    {profile?.current_company || latestExperience?.company || (hasWorkExperience
                                        ? 'Company not specified'
                                        : 'Fresher')}
                                </span>
                            </span>

                            {/* Experience Duration OR Data Annotation - Conditional display */}
                            {hasWorkExperience ? (
                                <span className="profile-info-tag">
                                    <span className="tag-icon">⏳</span>
                                    <span className="tag-text">
                                        {profile?.years_of_experience
                                            ? `${profile.years_of_experience} years exp`
                                            : `${profile?.work_experience?.length || 1} position(s)`}
                                    </span>
                                </span>
                            ) : (
                                /* Data Annotation Interest - Only for freshers */
                                profile?.has_data_annotation_experience !== null && profile?.has_data_annotation_experience !== undefined && (
                                    <span className={`profile-info-tag ${profile.has_data_annotation_experience ? 'highlight' : ''}`}>
                                        <span className="tag-icon">🤖</span>
                                        <span className="tag-text">
                                            {profile.has_data_annotation_experience
                                                ? 'Data Annotation Exp.'
                                                : 'New to Data Annotation'}
                                        </span>
                                    </span>
                                )
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

            {/* Add/Edit Modal */}
            {showAddModal && (
                <div className="modal-overlay" onClick={closeModal}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h3>{editingItem ? 'Edit' : 'Add'} {showAddModal.charAt(0).toUpperCase() + showAddModal.slice(1)}</h3>
                            <button className="modal-close" onClick={closeModal}>×</button>
                        </div>
                        <div className="modal-body">
                            {/* Education Form */}
                            {showAddModal === 'education' && (
                                <>
                                    <div className="form-group">
                                        <label>School/University *</label>
                                        <input
                                            type="text"
                                            value={(formData.school as string) || ''}
                                            onChange={e => updateFormField('school', e.target.value)}
                                            placeholder="e.g. Harvard University"
                                        />
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>Degree</label>
                                            <input
                                                type="text"
                                                value={(formData.degree as string) || ''}
                                                onChange={e => updateFormField('degree', e.target.value)}
                                                placeholder="e.g. Bachelor of Science"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Field of Study</label>
                                            <input
                                                type="text"
                                                value={(formData.field_of_study as string) || ''}
                                                onChange={e => updateFormField('field_of_study', e.target.value)}
                                                placeholder="e.g. Computer Science"
                                            />
                                        </div>
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>Start Year</label>
                                            <input
                                                type="number"
                                                value={(formData.start_year as number) || ''}
                                                onChange={e => updateFormField('start_year', parseInt(e.target.value) || null)}
                                                placeholder="2018"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>End Year</label>
                                            <input
                                                type="number"
                                                value={(formData.end_year as number) || ''}
                                                onChange={e => updateFormField('end_year', parseInt(e.target.value) || null)}
                                                placeholder="2022"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>GPA</label>
                                            <input
                                                type="text"
                                                value={(formData.gpa as string) || ''}
                                                onChange={e => updateFormField('gpa', e.target.value)}
                                                placeholder="3.8"
                                            />
                                        </div>
                                    </div>
                                </>
                            )}

                            {/* Experience Form */}
                            {showAddModal === 'experience' && (
                                <>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>Company *</label>
                                            <input
                                                type="text"
                                                value={(formData.company as string) || ''}
                                                onChange={e => updateFormField('company', e.target.value)}
                                                placeholder="e.g. Google"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Role *</label>
                                            <input
                                                type="text"
                                                value={(formData.role as string) || ''}
                                                onChange={e => updateFormField('role', e.target.value)}
                                                placeholder="e.g. Software Engineer"
                                            />
                                        </div>
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>City</label>
                                            <input
                                                type="text"
                                                value={(formData.city as string) || ''}
                                                onChange={e => updateFormField('city', e.target.value)}
                                                placeholder="e.g. San Francisco"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>Country</label>
                                            <input
                                                type="text"
                                                value={(formData.country as string) || ''}
                                                onChange={e => updateFormField('country', e.target.value)}
                                                placeholder="e.g. USA"
                                            />
                                        </div>
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>Start Date</label>
                                            <input
                                                type="text"
                                                value={(formData.start_date as string) || ''}
                                                onChange={e => updateFormField('start_date', e.target.value)}
                                                placeholder="e.g. 2020-01"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>End Date</label>
                                            <input
                                                type="text"
                                                value={(formData.end_date as string) || ''}
                                                onChange={e => updateFormField('end_date', e.target.value)}
                                                placeholder="Leave empty if current"
                                                disabled={formData.is_current as boolean}
                                            />
                                        </div>
                                    </div>
                                    <div className="form-group checkbox">
                                        <label>
                                            <input
                                                type="checkbox"
                                                checked={(formData.is_current as boolean) || false}
                                                onChange={e => updateFormField('is_current', e.target.checked)}
                                            />
                                            Currently working here
                                        </label>
                                    </div>
                                    <div className="form-group">
                                        <label>Description</label>
                                        <textarea
                                            value={(formData.description as string) || ''}
                                            onChange={e => updateFormField('description', e.target.value)}
                                            placeholder="Describe your responsibilities and achievements..."
                                            rows={4}
                                        />
                                    </div>
                                </>
                            )}

                            {/* Project Form */}
                            {showAddModal === 'project' && (
                                <>
                                    <div className="form-group">
                                        <label>Project Name *</label>
                                        <input
                                            type="text"
                                            value={(formData.name as string) || ''}
                                            onChange={e => updateFormField('name', e.target.value)}
                                            placeholder="e.g. E-commerce Platform"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Description</label>
                                        <textarea
                                            value={(formData.description as string) || ''}
                                            onChange={e => updateFormField('description', e.target.value)}
                                            placeholder="Describe the project..."
                                            rows={3}
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Technologies (comma-separated)</label>
                                        <input
                                            type="text"
                                            value={(formData.technologies as string[])?.join(', ') || ''}
                                            onChange={e => updateFormField('technologies', e.target.value.split(',').map(t => t.trim()).filter(t => t))}
                                            placeholder="e.g. React, Node.js, PostgreSQL"
                                        />
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>Start Year</label>
                                            <input
                                                type="number"
                                                value={(formData.start_year as number) || ''}
                                                onChange={e => updateFormField('start_year', parseInt(e.target.value) || null)}
                                                placeholder="2023"
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>End Year</label>
                                            <input
                                                type="number"
                                                value={(formData.end_year as number) || ''}
                                                onChange={e => updateFormField('end_year', parseInt(e.target.value) || null)}
                                                placeholder="2024"
                                            />
                                        </div>
                                    </div>
                                    <div className="form-group">
                                        <label>Project URL</label>
                                        <input
                                            type="url"
                                            value={(formData.url as string) || ''}
                                            onChange={e => updateFormField('url', e.target.value)}
                                            placeholder="https://github.com/user/project"
                                        />
                                    </div>
                                </>
                            )}

                            {/* Skill Form */}
                            {showAddModal === 'skill' && (
                                <>
                                    <div className="form-group">
                                        <label>Skill Name *</label>
                                        <input
                                            type="text"
                                            value={(formData.name as string) || ''}
                                            onChange={e => updateFormField('name', e.target.value)}
                                            placeholder="e.g. Python, React, AWS"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Category</label>
                                        <select
                                            value={(formData.category as string) || 'other'}
                                            onChange={e => updateFormField('category', e.target.value)}
                                        >
                                            <option value="language">Programming Language</option>
                                            <option value="framework">Framework</option>
                                            <option value="database">Database</option>
                                            <option value="cloud">Cloud</option>
                                            <option value="tool">Tool</option>
                                            <option value="other">Other</option>
                                        </select>
                                    </div>
                                </>
                            )}
                        </div>
                        <div className="modal-footer">
                            <button className="btn-cancel" onClick={closeModal}>Cancel</button>
                            <button
                                className="btn-save"
                                onClick={handleFormSubmit}
                                disabled={formSaving || (showAddModal !== 'skill' && !formData[showAddModal === 'education' ? 'school' : showAddModal === 'experience' ? 'company' : 'name'])}
                            >
                                {formSaving ? 'Saving...' : (editingItem ? 'Update' : 'Add')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

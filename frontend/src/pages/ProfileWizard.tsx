import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { profileApi } from '../services/api';
import logoImg from '../assets/autonex_ai_cover.png';
import './ProfileWizard.css';

interface ProfileData {
    fullName: string;
    knowsDataAnnotation: string;
    whyAnnotation: string;
    resume: File | null;
}

export default function ProfileWizard() {
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [dragActive, setDragActive] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    const [profileData, setProfileData] = useState<ProfileData>({
        fullName: '',
        knowsDataAnnotation: '',
        whyAnnotation: '',
        resume: null
    });

    const updateField = (field: keyof ProfileData, value: any) => {
        setProfileData(prev => ({ ...prev, [field]: value }));
        setError(null);
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
            const file = e.dataTransfer.files[0];
            if (file.type === 'application/pdf') {
                updateField('resume', file);
            } else {
                setError('Please upload a PDF file');
            }
        }
    }, []);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            if (file.type === 'application/pdf') {
                updateField('resume', file);
            } else {
                setError('Please upload a PDF file');
            }
        }
    };

    const canSubmit = () => {
        return (
            profileData.fullName.trim() &&
            profileData.knowsDataAnnotation &&
            profileData.whyAnnotation.trim().length >= 10
        );
    };

    const handleSubmit = async () => {
        if (!canSubmit()) return;

        setLoading(true);
        setError(null);

        try {
            // First, save the user's name and wizard answers
            await profileApi.completeProfile(
                profileData.fullName.trim(),
                profileData.knowsDataAnnotation,
                profileData.whyAnnotation.trim()
            );

            // If resume is uploaded, parse it in background
            if (profileData.resume) {
                setUploading(true);
                setUploadProgress(10);

                const progressInterval = setInterval(() => {
                    setUploadProgress(prev => {
                        if (prev >= 90) {
                            clearInterval(progressInterval);
                            return prev;
                        }
                        return prev + 10;
                    });
                }, 300);

                try {
                    await profileApi.uploadResume(profileData.resume);
                    clearInterval(progressInterval);
                    setUploadProgress(100);
                } catch (err: any) {
                    clearInterval(progressInterval);
                    console.warn('Resume upload may still be processing:', err);
                }
            }

            // Navigate to dashboard immediately
            navigate('/dashboard');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Something went wrong. Please try again.');
        } finally {
            setLoading(false);
            setUploading(false);
        }
    };

    return (
        <div className="wizard-page">
            <div className="wizard-container">
                {/* Left Side - Branding */}
                <div className="wizard-sidebar">
                    <div className="sidebar-content">
                        <img src={logoImg} alt="Logo" className="wizard-logo" />
                        <h1 className="wizard-sidebar-title">
                            Set Up Your<br />Profile 🚀
                        </h1>
                        <p className="wizard-sidebar-subtitle">
                            Unlock personalized job matches and AI-powered insights in minutes.
                        </p>
                    </div>

                    <div className="wizard-features">
                        <div className="feature-item">
                            <span className="feature-icon">⚡</span>
                            <div className="feature-text">
                                <strong>Quick Setup</strong>
                                <p>Takes less than 60 seconds</p>
                            </div>
                        </div>
                        <div className="feature-item">
                            <span className="feature-icon">🤖</span>
                            <div className="feature-text">
                                <strong>AI-Powered</strong>
                                <p>Auto-extraction from resume</p>
                            </div>
                        </div>
                        <div className="feature-item">
                            <span className="feature-icon">🎯</span>
                            <div className="feature-text">
                                <strong>Personalized</strong>
                                <p>Tailored job recommendations</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Side - Form */}
                <div className="wizard-main">
                    <div className="wizard-card">
                        <div className="wizard-header">
                            <h2>Complete Your Profile</h2>
                            <p>Fill in your details to get started</p>
                        </div>

                        {error && (
                            <div className="wizard-error">
                                <span>⚠️ {error}</span>
                                <button onClick={() => setError(null)}>×</button>
                            </div>
                        )}

                        <div className="wizard-form">
                            {/* Name Field */}
                            <div className="form-group">
                                <label className="form-label">
                                    <span className="label-icon">👤</span>
                                    Full Name
                                    <span className="required">*</span>
                                </label>
                                <input
                                    type="text"
                                    className="form-input"
                                    placeholder="Enter your full name"
                                    value={profileData.fullName}
                                    onChange={(e) => updateField('fullName', e.target.value)}
                                    autoFocus
                                />
                            </div>

                            {/* Data Annotation Question */}
                            <div className="form-group">
                                <label className="form-label">
                                    <span className="label-icon">📊</span>
                                    Do you have experience with Data Annotation?
                                    <span className="required">*</span>
                                </label>
                                <div className="option-cards">
                                    <button
                                        type="button"
                                        className={`option-card ${profileData.knowsDataAnnotation === 'yes' ? 'selected' : ''}`}
                                        onClick={() => updateField('knowsDataAnnotation', 'yes')}
                                    >
                                        <span className="option-icon">✅</span>
                                        <span className="option-title">Yes, I have experience</span>
                                        <span className="option-desc">I've worked on data annotation projects</span>
                                    </button>
                                    <button
                                        type="button"
                                        className={`option-card ${profileData.knowsDataAnnotation === 'no' ? 'selected' : ''}`}
                                        onClick={() => updateField('knowsDataAnnotation', 'no')}
                                    >
                                        <span className="option-icon">🌱</span>
                                        <span className="option-title">I'm new to this</span>
                                        <span className="option-desc">Eager to learn and get started</span>
                                    </button>
                                </div>
                            </div>

                            {/* Why Annotation Question */}
                            <div className="form-group">
                                <label className="form-label">
                                    <span className="label-icon">💭</span>
                                    Why do you want to work in Annotation?
                                    <span className="required">*</span>
                                </label>
                                <textarea
                                    className="form-textarea"
                                    placeholder="Share your motivation in a few sentences..."
                                    rows={3}
                                    value={profileData.whyAnnotation}
                                    onChange={(e) => updateField('whyAnnotation', e.target.value)}
                                />
                                <span className="char-count">
                                    {profileData.whyAnnotation.length} / 10 min characters
                                </span>
                            </div>

                            {/* Resume Upload */}
                            <div className="form-group">
                                <label className="form-label">
                                    <span className="label-icon">📄</span>
                                    Upload Resume
                                    <span className="optional">(Recommended)</span>
                                </label>
                                <div
                                    className={`resume-dropzone ${dragActive ? 'drag-active' : ''} ${profileData.resume ? 'has-file' : ''}`}
                                    onDragEnter={handleDrag}
                                    onDragLeave={handleDrag}
                                    onDragOver={handleDrag}
                                    onDrop={handleDrop}
                                >
                                    <input
                                        type="file"
                                        id="resume"
                                        accept=".pdf"
                                        onChange={handleFileChange}
                                        className="file-input-hidden"
                                    />
                                    <label htmlFor="resume" className="dropzone-content">
                                        {profileData.resume ? (
                                            <>
                                                <span className="file-icon">📄</span>
                                                <span className="file-name">{profileData.resume.name}</span>
                                                <span className="file-size">
                                                    {(profileData.resume.size / 1024 / 1024).toFixed(2)} MB
                                                </span>
                                                <button
                                                    type="button"
                                                    className="remove-file"
                                                    onClick={(e) => {
                                                        e.preventDefault();
                                                        e.stopPropagation();
                                                        updateField('resume', null);
                                                    }}
                                                >
                                                    Remove
                                                </button>
                                            </>
                                        ) : (
                                            <>
                                                <span className="upload-icon">📤</span>
                                                <span className="upload-text">
                                                    Drag & drop your resume here
                                                </span>
                                                <span className="upload-hint">
                                                    or click to browse • PDF only
                                                </span>
                                            </>
                                        )}
                                    </label>
                                </div>
                                <p className="form-hint">
                                    💡 AI will extract your skills, experience & education automatically
                                </p>
                            </div>

                            {/* Upload Progress */}
                            {uploading && (
                                <div className="upload-progress-bar">
                                    <div
                                        className="progress-fill"
                                        style={{ width: `${uploadProgress}%` }}
                                    />
                                    <span className="progress-text">
                                        {uploadProgress < 100 ? '🤖 Parsing resume with AI...' : '✅ Done!'}
                                    </span>
                                </div>
                            )}

                            {/* Submit Button */}
                            <button
                                type="button"
                                className="btn-submit"
                                onClick={handleSubmit}
                                disabled={!canSubmit() || loading}
                            >
                                {loading ? (
                                    <>
                                        <span className="spinner" />
                                        {uploading ? 'Processing Resume...' : 'Setting up...'}
                                    </>
                                ) : (
                                    <>
                                        Complete & Get Started
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z" />
                                        </svg>
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

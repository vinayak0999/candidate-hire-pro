import { useState, useEffect, useCallback, useMemo, memo, useRef } from 'react';
import { adminApiService } from '../../services/api';
import {
    Search, User, Mail, Phone, Calendar, GraduationCap, Building2,
    X, Send, MessageSquare, Eye, Clock, Download,
    CheckCircle, XCircle, FileText, ExternalLink, Briefcase, MapPin, Code
} from 'lucide-react';

import './CandidatesPage.css';

// ===== TYPES =====
interface Candidate {
    id: number;
    name: string;
    email: string;
    phone?: string;
    avatar_url?: string;
    applied_job: string | null;
    progress: number;
    status: string;
    last_activity: string | null;
}

interface CandidateProfile {
    id: number;
    name: string;
    email: string;
    phone?: string;
    avatar_url?: string;
    registration_number: string;
    degree: string;
    branch: string;
    batch: string;
    college: string;
    created_at: string;
    is_active: boolean;
    neo_pat_score: number;
    solved_easy: number;
    solved_medium: number;
    solved_hard: number;
    badges_count: number;
    // Resume data
    resume_url?: string;
    resume_filename?: string;
    professional_summary?: string;
    skills?: string[];
    years_of_experience?: number;
    current_role?: string;
    current_company?: string;
    location?: string;
    linkedin_url?: string;
    github_url?: string;
    portfolio_url?: string;
    has_data_annotation_experience?: boolean;
    why_annotation?: string;
    education?: Array<{
        id: number;
        school: string;
        degree?: string;
        field_of_study?: string;
        start_year?: number;
        end_year?: number;
        gpa?: string;
    }>;
    work_experience?: Array<{
        id: number;
        company: string;
        role: string;
        city?: string;
        country?: string;
        start_date?: string;
        end_date?: string;
        is_current: boolean;
        description?: string;
    }>;
    projects?: Array<{
        id: number;
        name: string;
        description?: string;
        technologies: string[];
        url?: string;
    }>;
    test_attempts: Array<{
        test_id: number;
        status: string;
        score: number;
        started_at: string;
        completed_at: string;
    }>;
    messages: Array<{
        id: number;
        subject: string;
        reason: string;
        is_read: boolean;
        created_at: string;
    }>;
}


// ===== AVATAR COMPONENT =====
const Avatar = memo(({ name, avatarUrl, size = 40 }: { name: string; avatarUrl?: string; size?: number }) => {
    const initials = name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase();
    const colors = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6'];
    const colorIndex = name.charCodeAt(0) % colors.length;

    if (avatarUrl) {
        return <img src={avatarUrl} alt={name} className="avatar-img" style={{ width: size, height: size }} />;
    }
    return (
        <div className="avatar-initials" style={{ width: size, height: size, backgroundColor: colors[colorIndex] }}>
            {initials}
        </div>
    );
});

// ===== CANDIDATE ROW =====
const CandidateRow = memo(({
    candidate,
    onView,
    onMessage,
    onApprove,
    onReject
}: {
    candidate: Candidate;
    onView: (id: number) => void;
    onMessage: (id: number, name: string) => void;
    onApprove: (id: number) => void;
    onReject: (id: number) => void;
}) => {
    const statusColors: Record<string, { bg: string; text: string }> = {
        active: { bg: '#dcfce7', text: '#16a34a' },
        pending: { bg: '#fef3c7', text: '#d97706' },
        rejected: { bg: '#fee2e2', text: '#dc2626' },
        approved: { bg: '#dbeafe', text: '#2563eb' }
    };
    const statusStyle = statusColors[candidate.status] || statusColors.pending;

    return (
        <div className="candidate-row">
            <div className="candidate-info">
                <Avatar name={candidate.name} avatarUrl={candidate.avatar_url} size={44} />
                <div className="candidate-details">
                    <h4 className="candidate-name">{candidate.name}</h4>
                    <p className="candidate-email">{candidate.email}</p>
                </div>
            </div>

            <div className="candidate-meta">
                <span className="meta-item">
                    <GraduationCap size={14} />
                    {candidate.applied_job || 'Not Applied'}
                </span>
                {candidate.last_activity && (
                    <span className="meta-item">
                        <Clock size={14} />
                        {new Date(candidate.last_activity).toLocaleDateString()}
                    </span>
                )}
            </div>

            <div className="candidate-progress">
                <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${candidate.progress}%` }} />
                </div>
                <span className="progress-text">{candidate.progress}%</span>
            </div>

            <span className="status-badge" style={{ background: statusStyle.bg, color: statusStyle.text }}>
                {candidate.status}
            </span>

            <div className="candidate-actions">
                <button className="action-btn" onClick={() => onView(candidate.id)} title="View Profile">
                    <Eye size={16} />
                </button>
                <button className="action-btn" onClick={() => onMessage(candidate.id, candidate.name)} title="Send Message">
                    <MessageSquare size={16} />
                </button>
                {candidate.status === 'pending' && (
                    <>
                        <button className="action-btn success" onClick={() => onApprove(candidate.id)} title="Approve">
                            <CheckCircle size={16} />
                        </button>
                        <button className="action-btn danger" onClick={() => onReject(candidate.id)} title="Reject">
                            <XCircle size={16} />
                        </button>
                    </>
                )}
            </div>
        </div>
    );
});

// ===== MAIN COMPONENT =====
export default function CandidatesPage() {
    const [candidates, setCandidates] = useState<Candidate[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');

    // Profile drawer
    const [selectedCandidate, setSelectedCandidate] = useState<CandidateProfile | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [profileLoading, setProfileLoading] = useState(false);
    const [showResume, setShowResume] = useState(false);
    const [downloadingResume, setDownloadingResume] = useState(false);

    // Message modal
    const [messageModal, setMessageModal] = useState<{ open: boolean; candidateId: number; candidateName: string }>({
        open: false, candidateId: 0, candidateName: ''
    });
    const [messageForm, setMessageForm] = useState({ subject: '', content: '', reason: '' });
    const [sending, setSending] = useState(false);

    // Debounced search
    const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

    // Fetch candidates
    const fetchCandidates = useCallback(async () => {
        setLoading(true);
        try {
            const data = await adminApiService.getCandidates(statusFilter === 'all' ? undefined : statusFilter);
            setCandidates(data);
        } catch (error) {
            console.error('Failed to fetch candidates:', error);
        } finally {
            setLoading(false);
        }
    }, [statusFilter]);

    useEffect(() => {
        fetchCandidates();
    }, [fetchCandidates]);

    // Filtered candidates (memoized for 10k+ performance)
    const filteredCandidates = useMemo(() => {
        if (!searchQuery.trim()) return candidates;
        const query = searchQuery.toLowerCase();
        return candidates.filter(c =>
            c.name.toLowerCase().includes(query) ||
            c.email.toLowerCase().includes(query) ||
            (c.applied_job && c.applied_job.toLowerCase().includes(query))
        );
    }, [candidates, searchQuery]);

    // Debounced search handler
    const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value;
        if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
        searchTimeoutRef.current = setTimeout(() => {
            setSearchQuery(value);
        }, 300); // 300ms debounce
    }, []);

    // View profile
    const handleViewProfile = useCallback(async (candidateId: number) => {
        setProfileLoading(true);
        setDrawerOpen(true);
        try {
            const profile = await adminApiService.getCandidateProfile(candidateId);
            setSelectedCandidate(profile);
        } catch (error) {
            console.error('Failed to load profile:', error);
        } finally {
            setProfileLoading(false);
        }
    }, []);

    // Open message modal
    const handleOpenMessage = useCallback((candidateId: number, candidateName: string) => {
        setMessageModal({ open: true, candidateId, candidateName });
        setMessageForm({ subject: '', content: '', reason: '' });
    }, []);

    // Send message
    const handleSendMessage = useCallback(async () => {
        if (!messageForm.subject.trim() || !messageForm.content.trim()) {
            alert('Please enter subject and message');
            return;
        }
        setSending(true);
        try {
            await adminApiService.sendMessage({
                recipient_id: messageModal.candidateId,
                subject: messageForm.subject,
                content: messageForm.content,
                reason: messageForm.reason || undefined
            });
            alert('Message sent successfully!');
            setMessageModal({ open: false, candidateId: 0, candidateName: '' });
        } catch (error) {
            alert('Failed to send message');
        } finally {
            setSending(false);
        }
    }, [messageModal.candidateId, messageForm]);

    // Approve/Reject
    const handleApprove = useCallback(async (id: number) => {
        try {
            await adminApiService.approveCandidate(id);
            setCandidates(prev => prev.map(c => c.id === id ? { ...c, status: 'approved' } : c));
        } catch (error) { console.error('Approve failed:', error); }
    }, []);

    const handleReject = useCallback(async (id: number) => {
        try {
            await adminApiService.rejectCandidate(id);
            setCandidates(prev => prev.map(c => c.id === id ? { ...c, status: 'rejected' } : c));
        } catch (error) { console.error('Reject failed:', error); }
    }, []);

    // Download candidate resume
    const handleDownloadResume = useCallback(async () => {
        if (!selectedCandidate) return;
        try {
            setDownloadingResume(true);
            const blob = await adminApiService.downloadCandidateResume(selectedCandidate.id);
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = selectedCandidate.resume_filename || `${selectedCandidate.name}_resume.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('Download failed:', error);
            alert('Failed to download resume');
        } finally {
            setDownloadingResume(false);
        }
    }, [selectedCandidate]);

    const MESSAGE_REASONS = [
        'Interview Invitation',
        'Application Update',
        'Document Request',
        'Test Information',
        'General Inquiry',
        'Other'
    ];

    return (
        <div className="candidates-page">
            <header className="page-header">
                <h1>Candidates</h1>
                <span className="candidate-count">{filteredCandidates.length} candidates</span>
            </header>

            {/* Toolbar */}
            <div className="candidates-toolbar">
                <div className="search-box">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="Search by name, email, or job..."
                        defaultValue={searchQuery}
                        onChange={handleSearchChange}
                    />
                </div>
                <div className="filter-tabs">
                    {['all', 'pending', 'approved', 'rejected'].map(status => (
                        <button
                            key={status}
                            className={`filter-tab ${statusFilter === status ? 'active' : ''}`}
                            onClick={() => setStatusFilter(status)}
                        >
                            {status.charAt(0).toUpperCase() + status.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            {/* Candidates List */}
            <div className="candidates-list">
                {loading ? (
                    <div className="loading-state">Loading candidates...</div>
                ) : filteredCandidates.length === 0 ? (
                    <div className="empty-state">
                        <User size={48} />
                        <p>No candidates found</p>
                    </div>
                ) : (
                    filteredCandidates.map(c => (
                        <CandidateRow
                            key={c.id}
                            candidate={c}
                            onView={handleViewProfile}
                            onMessage={handleOpenMessage}
                            onApprove={handleApprove}
                            onReject={handleReject}
                        />
                    ))
                )}
            </div>

            {/* Profile Drawer */}
            {drawerOpen && (
                <div className="drawer-overlay" onClick={() => setDrawerOpen(false)}>
                    <div className="profile-drawer profile-drawer-wide" onClick={e => e.stopPropagation()}>
                        <div className="drawer-header">
                            <h2>Candidate Profile</h2>
                            <button className="close-btn" onClick={() => setDrawerOpen(false)}><X size={20} /></button>
                        </div>

                        {profileLoading ? (
                            <div className="loading-state">Loading profile...</div>
                        ) : selectedCandidate && (
                            <div className="drawer-content drawer-content-two-col">
                                {/* Left Column - Parsed Data */}
                                <div className="drawer-data-column">
                                    {/* Profile Header */}
                                    <div className="profile-header">
                                        <Avatar name={selectedCandidate.name} avatarUrl={selectedCandidate.avatar_url} size={80} />
                                        <div>
                                            <h3>{selectedCandidate.name}</h3>
                                            <p className="registration">{selectedCandidate.registration_number}</p>
                                            {selectedCandidate.current_role && (
                                                <p className="current-role">
                                                    <Briefcase size={14} />
                                                    {selectedCandidate.current_role}
                                                    {selectedCandidate.current_company && ` at ${selectedCandidate.current_company}`}
                                                </p>
                                            )}
                                            {selectedCandidate.location && (
                                                <p className="location">
                                                    <MapPin size={14} />
                                                    {selectedCandidate.location}
                                                </p>
                                            )}
                                        </div>
                                    </div>

                                    {/* Contact Info */}
                                    <div className="profile-section">
                                        <h4>Contact Information</h4>
                                        <div className="info-grid">
                                            <div className="info-item">
                                                <Mail size={16} />
                                                <span>{selectedCandidate.email}</span>
                                            </div>
                                            <div className="info-item">
                                                <Phone size={16} />
                                                <span>{selectedCandidate.phone || 'Not provided'}</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Professional Summary */}
                                    {selectedCandidate.professional_summary && (
                                        <div className="profile-section">
                                            <h4><Briefcase size={16} /> Professional Summary</h4>
                                            <p className="summary-text">{selectedCandidate.professional_summary}</p>
                                        </div>
                                    )}

                                    {/* Work Experience */}
                                    {selectedCandidate.work_experience && selectedCandidate.work_experience.length > 0 && (
                                        <div className="profile-section">
                                            <h4><Building2 size={16} /> Work Experience</h4>
                                            <div className="experience-list">
                                                {selectedCandidate.work_experience.map(exp => (
                                                    <div key={exp.id} className="experience-item">
                                                        <div className="experience-header">
                                                            <strong>{exp.role}</strong>
                                                            <span className="company-name">{exp.company}</span>
                                                        </div>
                                                        <div className="experience-meta">
                                                            {exp.city && exp.country && <span>{exp.city}, {exp.country}</span>}
                                                            <span className="date-range">
                                                                {exp.start_date} - {exp.is_current ? 'Present' : exp.end_date}
                                                            </span>
                                                        </div>
                                                        {exp.description && (
                                                            <p className="experience-desc">{exp.description}</p>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Education - from signup info */}
                                    <div className="profile-section">
                                        <h4><GraduationCap size={16} /> Education</h4>
                                        <div className="info-grid">
                                            <div className="info-item">
                                                <GraduationCap size={16} />
                                                <span>{selectedCandidate.degree} - {selectedCandidate.branch}</span>
                                            </div>
                                            <div className="info-item">
                                                <Building2 size={16} />
                                                <span>{selectedCandidate.college}</span>
                                            </div>
                                            <div className="info-item">
                                                <Calendar size={16} />
                                                <span>Batch: {selectedCandidate.batch}</span>
                                            </div>
                                        </div>
                                        {/* Additional education from resume */}
                                        {selectedCandidate.education && selectedCandidate.education.length > 0 && (
                                            <div className="education-list">
                                                {selectedCandidate.education.map(edu => (
                                                    <div key={edu.id} className="education-item">
                                                        <strong>{edu.degree} {edu.field_of_study && `in ${edu.field_of_study}`}</strong>
                                                        <span>{edu.school}</span>
                                                        <span className="date-range">{edu.start_year} - {edu.end_year}</span>
                                                        {edu.gpa && <span className="gpa">GPA: {edu.gpa}</span>}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {/* Skills */}
                                    {selectedCandidate.skills && selectedCandidate.skills.length > 0 && (
                                        <div className="profile-section">
                                            <h4><Code size={16} /> Skills</h4>
                                            <div className="skills-grid">
                                                {selectedCandidate.skills.map((skill, i) => (
                                                    <span key={i} className="skill-tag">{skill}</span>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Projects */}
                                    {selectedCandidate.projects && selectedCandidate.projects.length > 0 && (
                                        <div className="profile-section">
                                            <h4>Projects</h4>
                                            <div className="projects-list">
                                                {selectedCandidate.projects.map(proj => (
                                                    <div key={proj.id} className="project-item">
                                                        <div className="project-header">
                                                            <strong>{proj.name}</strong>
                                                            {proj.url && (
                                                                <a href={proj.url} target="_blank" rel="noopener noreferrer">
                                                                    <ExternalLink size={14} />
                                                                </a>
                                                            )}
                                                        </div>
                                                        {proj.description && <p>{proj.description}</p>}
                                                        {proj.technologies.length > 0 && (
                                                            <div className="project-tech">
                                                                {proj.technologies.map((tech, i) => (
                                                                    <span key={i} className="tech-tag">{tech}</span>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Stats */}
                                    <div className="profile-section">
                                        <h4>Performance Stats</h4>
                                        <div className="stats-grid">
                                            <div className="stat-card">
                                                <span className="stat-value">{selectedCandidate.neo_pat_score}</span>
                                                <span className="stat-label">Score</span>
                                            </div>
                                            <div className="stat-card easy">
                                                <span className="stat-value">{selectedCandidate.solved_easy}</span>
                                                <span className="stat-label">Easy</span>
                                            </div>
                                            <div className="stat-card medium">
                                                <span className="stat-value">{selectedCandidate.solved_medium}</span>
                                                <span className="stat-label">Medium</span>
                                            </div>
                                            <div className="stat-card hard">
                                                <span className="stat-value">{selectedCandidate.solved_hard}</span>
                                                <span className="stat-label">Hard</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Test Attempts */}
                                    {selectedCandidate.test_attempts.length > 0 && (
                                        <div className="profile-section">
                                            <h4>Test History</h4>
                                            <div className="test-list">
                                                {selectedCandidate.test_attempts.map((test, i) => (
                                                    <div key={i} className="test-item">
                                                        <span className="test-id">Test #{test.test_id}</span>
                                                        <span className={`test-status ${test.status}`}>{test.status}</span>
                                                        <span className="test-score">{test.score} pts</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Links */}
                                    {(selectedCandidate.linkedin_url || selectedCandidate.github_url || selectedCandidate.portfolio_url) && (
                                        <div className="profile-section">
                                            <h4>Links</h4>
                                            <div className="links-grid">
                                                {selectedCandidate.linkedin_url && (
                                                    <a href={selectedCandidate.linkedin_url} target="_blank" rel="noopener noreferrer" className="link-item">
                                                        <ExternalLink size={14} /> LinkedIn
                                                    </a>
                                                )}
                                                {selectedCandidate.github_url && (
                                                    <a href={selectedCandidate.github_url} target="_blank" rel="noopener noreferrer" className="link-item">
                                                        <ExternalLink size={14} /> GitHub
                                                    </a>
                                                )}
                                                {selectedCandidate.portfolio_url && (
                                                    <a href={selectedCandidate.portfolio_url} target="_blank" rel="noopener noreferrer" className="link-item">
                                                        <ExternalLink size={14} /> Portfolio
                                                    </a>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {/* Messages Sent */}
                                    {selectedCandidate.messages.length > 0 && (
                                        <div className="profile-section">
                                            <h4>Messages Sent</h4>
                                            <div className="messages-list">
                                                {selectedCandidate.messages.map(msg => (
                                                    <div key={msg.id} className="message-item">
                                                        <span className="msg-subject">{msg.subject}</span>
                                                        <span className="msg-date">{new Date(msg.created_at).toLocaleDateString()}</span>
                                                        {!msg.is_read && <span className="unread-dot" />}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>

                                {/* Right Column - Resume Viewer */}
                                <div className="drawer-resume-column">
                                    <div className="resume-section-header">
                                        <h4><FileText size={16} /> Resume</h4>
                                        {selectedCandidate.resume_url && (
                                            <div className="resume-actions">
                                                <button
                                                    className="btn-outline btn-sm"
                                                    onClick={handleDownloadResume}
                                                    disabled={downloadingResume}
                                                >
                                                    <Download size={14} />
                                                    {downloadingResume ? 'Downloading...' : 'Download'}
                                                </button>
                                                <a
                                                    href={selectedCandidate.resume_url.startsWith('/uploads/')
                                                        ? `${import.meta.env.VITE_API_URL?.replace('/api', '') || 'http://localhost:8000'}${selectedCandidate.resume_url}`
                                                        : selectedCandidate.resume_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="btn-outline btn-sm"
                                                >
                                                    <ExternalLink size={14} /> Open
                                                </a>
                                            </div>
                                        )}
                                    </div>
                                    {selectedCandidate.resume_url ? (
                                        <div className="resume-viewer-container">
                                            {/* Use Google PDF Viewer for reliable cross-origin PDF rendering */}
                                            {selectedCandidate.resume_url.startsWith('/uploads/') ? (
                                                // Local storage - show download prompt since iframe won't work
                                                <div className="local-resume-notice">
                                                    <FileText size={48} strokeWidth={1} />
                                                    <p>Resume stored locally</p>
                                                    <p className="subtext">Click "Download" or "Open" above to view the PDF</p>
                                                    <button
                                                        className="btn-primary btn-sm"
                                                        onClick={handleDownloadResume}
                                                        disabled={downloadingResume}
                                                    >
                                                        <Download size={14} />
                                                        {downloadingResume ? 'Downloading...' : 'Download Resume'}
                                                    </button>
                                                </div>
                                            ) : (
                                                // Remote URL (Supabase/CloudFront) - try iframe with fallback
                                                <iframe
                                                    src={selectedCandidate.resume_url}
                                                    title="Resume"
                                                    className="resume-iframe"
                                                    onError={() => console.log('PDF iframe failed to load')}
                                                />
                                            )}
                                        </div>
                                    ) : (
                                        <div className="no-resume">
                                            <FileText size={48} strokeWidth={1} />
                                            <p>No resume uploaded</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Drawer Actions */}
                        {selectedCandidate && (
                            <div className="drawer-actions">
                                <button className="btn-secondary" onClick={() => handleOpenMessage(selectedCandidate.id, selectedCandidate.name)}>
                                    <MessageSquare size={16} /> Send Message
                                </button>
                            </div>
                        )}
                    </div>
                </div>

            )}

            {/* Message Modal */}
            {messageModal.open && (
                <div className="modal-overlay" onClick={() => setMessageModal({ open: false, candidateId: 0, candidateName: '' })}>
                    <div className="message-modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Send Message to {messageModal.candidateName}</h2>
                            <button className="close-btn" onClick={() => setMessageModal({ open: false, candidateId: 0, candidateName: '' })}>
                                <X size={20} />
                            </button>
                        </div>
                        <div className="modal-body">
                            <div className="form-group">
                                <label>Reason</label>
                                <select value={messageForm.reason} onChange={e => setMessageForm(p => ({ ...p, reason: e.target.value }))}>
                                    <option value="">Select a reason...</option>
                                    {MESSAGE_REASONS.map(r => <option key={r} value={r}>{r}</option>)}
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Subject *</label>
                                <input
                                    placeholder="Message subject"
                                    value={messageForm.subject}
                                    onChange={e => setMessageForm(p => ({ ...p, subject: e.target.value }))}
                                />
                            </div>
                            <div className="form-group">
                                <label>Message *</label>
                                <textarea
                                    rows={5}
                                    placeholder="Type your message here..."
                                    value={messageForm.content}
                                    onChange={e => setMessageForm(p => ({ ...p, content: e.target.value }))}
                                />
                            </div>
                        </div>
                        <div className="modal-footer">
                            <button className="btn-secondary" onClick={() => setMessageModal({ open: false, candidateId: 0, candidateName: '' })}>
                                Cancel
                            </button>
                            <button className="btn-primary" onClick={handleSendMessage} disabled={sending}>
                                <Send size={16} />
                                {sending ? 'Sending...' : 'Send Message'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Resume Viewer Modal */}
            {showResume && selectedCandidate?.resume_url && (
                <div className="modal-overlay resume-modal-overlay" onClick={() => setShowResume(false)}>
                    <div className="resume-modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2><FileText size={20} /> Resume - {selectedCandidate.name}</h2>
                            <button className="close-btn" onClick={() => setShowResume(false)}>
                                <X size={20} />
                            </button>
                        </div>
                        <div className="resume-viewer">
                            {selectedCandidate.resume_url.startsWith('/uploads/') ? (
                                <div className="local-resume-notice">
                                    <FileText size={48} strokeWidth={1} />
                                    <p>Resume stored locally</p>
                                    <p className="subtext">Click download to view the PDF</p>
                                    <button
                                        className="btn-primary btn-sm"
                                        onClick={handleDownloadResume}
                                        disabled={downloadingResume}
                                    >
                                        <Download size={14} />
                                        {downloadingResume ? 'Downloading...' : 'Download Resume'}
                                    </button>
                                </div>
                            ) : (
                                <iframe
                                    src={selectedCandidate.resume_url}
                                    title="Resume"
                                    className="resume-iframe"
                                />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

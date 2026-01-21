import { useState, useEffect, useCallback, useMemo, memo, useRef } from 'react';
import { adminApiService } from '../../services/api';
import {
    Search, User, Mail, Phone, Calendar, GraduationCap, Building2,
    X, Send, MessageSquare, Eye, Clock,
    CheckCircle, XCircle
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
                    <div className="profile-drawer" onClick={e => e.stopPropagation()}>
                        <div className="drawer-header">
                            <h2>Candidate Profile</h2>
                            <button className="close-btn" onClick={() => setDrawerOpen(false)}><X size={20} /></button>
                        </div>

                        {profileLoading ? (
                            <div className="loading-state">Loading profile...</div>
                        ) : selectedCandidate && (
                            <div className="drawer-content">
                                {/* Profile Header */}
                                <div className="profile-header">
                                    <Avatar name={selectedCandidate.name} avatarUrl={selectedCandidate.avatar_url} size={80} />
                                    <div>
                                        <h3>{selectedCandidate.name}</h3>
                                        <p className="registration">{selectedCandidate.registration_number}</p>
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

                                {/* Education */}
                                <div className="profile-section">
                                    <h4>Education</h4>
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
                                </div>

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

                                {/* Actions */}
                                <div className="drawer-actions">
                                    <button className="btn-secondary" onClick={() => handleOpenMessage(selectedCandidate.id, selectedCandidate.name)}>
                                        <MessageSquare size={16} /> Send Message
                                    </button>
                                </div>
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
        </div>
    );
}

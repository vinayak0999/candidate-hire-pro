import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { API_BASE_URL } from '../services/api';
import { Clock, FileText, Award, Play, CheckCircle, XCircle, BookOpen, Brain, Target, Trophy, X, RotateCcw, Home } from 'lucide-react';
import './Assessments.css';

interface Assessment {
    id: number;
    title: string;
    description: string | null;
    category: string | null;
    duration_minutes: number;
    total_questions: number;
    total_marks: number;
    passing_marks: number;
    status?: string;
    best_score?: number;
    best_percentage?: number;
    last_attempt_at?: string;
}

interface HistoryItem {
    id: number;
    test_id: number;
    test_title: string;
    status: string;
    score: number;
    total_marks: number;
    percentage: number;
    passed: boolean;
    started_at: string;
    completed_at: string;
}

interface AssessmentResult {
    attempt_id: number;
    assessment_id: number;
    assessment_title: string;
    category?: string;
    score: number;
    total_marks: number;
    percentage: number;
    passed: boolean;
    time_taken_seconds: number;
    sections?: Array<{
        section_id: number;
        section_title: string;
        total_marks: number;
        marks_obtained: number;
        questions: Array<{
            question_id: number;
            question_number?: string;
            question_text: string;
            user_answer?: string;
            correct_answer: string;
            is_correct: boolean;
            marks_obtained: number;
            max_marks: number;
        }>;
    }>;
}

type TabType = 'available' | 'history';

export default function Assessments() {
    const navigate = useNavigate();
    const location = useLocation();
    const [activeTab, setActiveTab] = useState<TabType>('available');
    const [assessments, setAssessments] = useState<Assessment[]>([]);
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [loading, setLoading] = useState(true);


    // Result modal state
    const [showResultModal, setShowResultModal] = useState(false);
    const [currentResult, setCurrentResult] = useState<AssessmentResult | null>(null);

    // Stats
    const [stats, setStats] = useState({
        total_available: 0,
        completed: 0,
        passed: 0,
        in_progress: 0,
    });

    // Check for result from navigation
    useEffect(() => {
        const state = location.state as { showResult?: boolean; result?: AssessmentResult } | null;
        if (state?.showResult && state?.result) {
            setCurrentResult(state.result);
            setShowResultModal(true);
            // Clear the state to prevent showing again on refresh
            window.history.replaceState({}, document.title);
        }
    }, [location]);

    useEffect(() => {
        loadData();
    }, []);

    useEffect(() => {
        if (activeTab === 'history' && history.length === 0) {
            loadHistory();
        }
    }, [activeTab]);

    const loadData = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('access_token');
            const res = await fetch(`${API_BASE_URL}/standalone-assessments/candidate/available`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setAssessments(data);

                // Calculate stats
                const completed = data.filter((a: Assessment) => a.status === 'completed').length;
                const passed = data.filter((a: Assessment) => a.best_percentage && a.best_percentage >= 60).length;
                const inProgress = data.filter((a: Assessment) => a.status === 'in_progress').length;

                setStats({
                    total_available: data.length,
                    completed,
                    passed,
                    in_progress: inProgress,
                });
            }
        } catch (error) {
            console.error('Failed to load assessments:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadHistory = async () => {
        try {
            const token = localStorage.getItem('access_token');
            const res = await fetch(`${API_BASE_URL}/standalone-assessments/candidate/history`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setHistory(data);
            }
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    };

    const handleStartTest = (assessmentId: number) => {
        navigate(`/test/assessment/${assessmentId}`);
    };

    const handleViewResult = async (attemptId: number) => {
        try {
            const token = localStorage.getItem('access_token');
            const res = await fetch(`${API_BASE_URL}/standalone-assessments/candidate/results/${attemptId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const result = await res.json();
                setCurrentResult(result);
                setShowResultModal(true);
            } else {
                // Fallback to test-result page for non-standalone tests
                navigate(`/test-result/${attemptId}`);
            }
        } catch (error) {
            console.error('Failed to fetch result:', error);
            navigate(`/test-result/${attemptId}`);
        }
    };

    const getCategoryIcon = (category: string | null) => {
        switch (category?.toLowerCase()) {
            case 'english': return <BookOpen size={24} />;
            case 'logical': return <Brain size={24} />;
            case 'technical': return <Target size={24} />;
            case 'aptitude': return <Trophy size={24} />;
            default: return <FileText size={24} />;
        }
    };

    const getCategoryClass = (category: string | null) => {
        switch (category?.toLowerCase()) {
            case 'english': return 'english';
            case 'logical': return 'logical';
            case 'technical': return 'technical';
            case 'aptitude': return 'aptitude';
            default: return 'default';
        }
    };

    const getStatusBadge = (assessment: Assessment) => {
        if (assessment.status === 'completed') {
            const passed = assessment.best_percentage && assessment.best_percentage >= 60;
            return (
                <div className="assessment-status">
                    <span className={`status-badge ${passed ? 'passed' : 'failed'}`}>
                        {passed ? 'Passed' : 'Failed'}
                    </span>
                    <span className="assessment-score">{assessment.best_percentage?.toFixed(0)}%</span>
                </div>
            );
        }
        if (assessment.status === 'in_progress') {
            return (
                <div className="assessment-status">
                    <span className="status-badge in-progress">In Progress</span>
                </div>
            );
        }
        return (
            <div className="assessment-status">
                <span className="status-badge not-started">Not Started</span>
            </div>
        );
    };



    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    };

    return (
        <div className="assessments-page">
            {/* Header */}
            <div className="assessments-header">
                <div>
                    <h1 className="assessments-title">Assessments</h1>
                    <p className="assessments-subtitle">Test your skills and earn certifications</p>
                </div>
            </div>

            {/* Tabs */}
            <div className="assessments-tabs-container">
                <div className="assessments-tabs">
                    <button
                        className={`assessments-tab ${activeTab === 'available' ? 'active' : ''}`}
                        onClick={() => setActiveTab('available')}
                    >
                        Available Tests
                    </button>
                    <button
                        className={`assessments-tab ${activeTab === 'history' ? 'active' : ''}`}
                        onClick={() => setActiveTab('history')}
                    >
                        My Results
                    </button>
                </div>
            </div>

            <div className="assessments-content">
                <div className="assessments-main">


                    {/* Available Tests Tab */}
                    {activeTab === 'available' && (
                        loading ? (
                            <div className="loading-state">Loading assessments...</div>
                        ) : assessments.length === 0 ? (
                            <div className="empty-state">
                                <FileText size={64} className="empty-state-icon" />
                                <p className="empty-state-text">No assessments available</p>
                            </div>
                        ) : (
                            <div className="assessments-grid">
                                {assessments.map(assessment => (
                                    <div key={assessment.id} className="assessment-card">
                                        <div className="assessment-card-header">
                                            <div className={`assessment-icon ${getCategoryClass(assessment.category)}`}>
                                                {getCategoryIcon(assessment.category)}
                                            </div>
                                            <div className="assessment-card-info">
                                                <span className={`assessment-category ${getCategoryClass(assessment.category)}`}>
                                                    {assessment.category || 'General'}
                                                </span>
                                                <h3 className="assessment-title">{assessment.title}</h3>
                                            </div>
                                        </div>

                                        {assessment.description && (
                                            <p className="assessment-desc">{assessment.description}</p>
                                        )}

                                        <div className="assessment-meta">
                                            <div className="assessment-meta-item">
                                                <Clock size={16} />
                                                <span>{assessment.duration_minutes} min</span>
                                            </div>
                                            <div className="assessment-meta-item">
                                                <FileText size={16} />
                                                <span>{assessment.total_questions} Qs</span>
                                            </div>
                                            <div className="assessment-meta-item">
                                                <Award size={16} />
                                                <span>{assessment.total_marks} marks</span>
                                            </div>
                                        </div>

                                        {getStatusBadge(assessment)}

                                        {assessment.status === 'completed' ? (
                                            <button
                                                className="btn-view-result"
                                                onClick={() => {
                                                    // Get the latest attempt from history and show result
                                                    loadHistory().then(() => {
                                                        const attemptForAssessment = history.find(h => h.test_id === assessment.id);
                                                        if (attemptForAssessment) {
                                                            handleViewResult(attemptForAssessment.id);
                                                        }
                                                    });
                                                }}
                                                disabled
                                                style={{ opacity: 0.7, cursor: 'not-allowed' }}
                                            >
                                                <CheckCircle size={18} /> Completed
                                            </button>
                                        ) : (
                                            <button
                                                className="btn-start-test"
                                                onClick={() => handleStartTest(assessment.id)}
                                            >
                                                <Play size={18} />
                                                {assessment.status === 'in_progress' ? 'Continue Test' : 'Start Test'}
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )
                    )}

                    {/* History Tab */}
                    {activeTab === 'history' && (
                        history.length === 0 ? (
                            <div className="empty-state">
                                <Trophy size={64} className="empty-state-icon" />
                                <p className="empty-state-text">No completed assessments yet</p>
                            </div>
                        ) : (
                            <div className="history-list">
                                {history.map(item => (
                                    <div
                                        key={item.id}
                                        className="history-card"
                                        onClick={() => handleViewResult(item.id)}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        <div className={`history-icon ${item.passed ? 'passed' : 'failed'}`}>
                                            {item.passed ? <CheckCircle size={24} /> : <XCircle size={24} />}
                                        </div>
                                        <div className="history-info">
                                            <h4 className="history-title">{item.test_title}</h4>
                                            <p className="history-date">
                                                Completed {item.completed_at ? formatDate(item.completed_at) : 'N/A'}
                                            </p>
                                        </div>
                                        <div className="history-score">
                                            <div className={`history-percentage ${item.passed ? 'passed' : 'failed'}`}>
                                                {item.percentage?.toFixed(0)}%
                                            </div>
                                            <div className="history-marks">
                                                {item.score}/{item.total_marks} marks
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )
                    )}
                </div>

                {/* Sidebar */}
                <div className="assessments-sidebar">
                    <div className="sidebar-card">
                        <h3 className="sidebar-title">Your Progress</h3>
                        <div className="stats-list">
                            <div className="stats-item">
                                <div className="stats-icon blue">
                                    <FileText size={22} />
                                </div>
                                <div className="stats-info">
                                    <span className="stats-label">Available Tests</span>
                                </div>
                                <span className="stats-value">{stats.total_available}</span>
                            </div>

                            <div className="stats-item">
                                <div className="stats-icon green">
                                    <CheckCircle size={22} />
                                </div>
                                <div className="stats-info">
                                    <span className="stats-label">Completed</span>
                                </div>
                                <span className="stats-value">{stats.completed}</span>
                            </div>

                            <div className="stats-item">
                                <div className="stats-icon purple">
                                    <Trophy size={22} />
                                </div>
                                <div className="stats-info">
                                    <span className="stats-label">Passed</span>
                                </div>
                                <span className="stats-value">{stats.passed}</span>
                            </div>

                            <div className="stats-item">
                                <div className="stats-icon amber">
                                    <Clock size={22} />
                                </div>
                                <div className="stats-info">
                                    <span className="stats-label">In Progress</span>
                                </div>
                                <span className="stats-value">{stats.in_progress}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Result Modal */}
            {showResultModal && currentResult && (
                <div className="result-modal-overlay" onClick={() => setShowResultModal(false)}>
                    <div className="result-modal" onClick={e => e.stopPropagation()}>
                        <button className="result-modal-close" onClick={() => setShowResultModal(false)}>
                            <X size={24} />
                        </button>

                        <div className="result-modal-header">
                            <h2>Test Completed</h2>
                            <p>Your test has been successfully submitted.</p>
                        </div>

                        <div className="result-modal-title">
                            {currentResult.assessment_title}
                        </div>

                        <div className="result-modal-score">
                            <div className={`score-circle ${currentResult.passed ? 'passed' : 'failed'}`}>
                                <span className="score-percentage">{currentResult.percentage.toFixed(0)}%</span>
                                <span className="score-label">Score</span>
                            </div>
                        </div>

                        <div className="result-modal-stats">
                            <div className="result-stat">
                                <span className="result-stat-value">{currentResult.score}/{currentResult.total_marks}</span>
                                <span className="result-stat-label">Marks</span>
                            </div>
                            <div className="result-stat">
                                <span className="result-stat-value">
                                    {Math.floor(currentResult.time_taken_seconds / 60)}m {currentResult.time_taken_seconds % 60}s
                                </span>
                                <span className="result-stat-label">Time Taken</span>
                            </div>
                        </div>

                        <div className={`result-status ${currentResult.passed ? 'passed' : 'failed'}`}>
                            {currentResult.passed ? (
                                <>
                                    <CheckCircle size={20} />
                                    <span>PASSED</span>
                                </>
                            ) : (
                                <>
                                    <XCircle size={20} />
                                    <span>NOT PASSED</span>
                                </>
                            )}
                        </div>

                        {/* Answer Review */}
                        {currentResult.sections && currentResult.sections.length > 0 && (
                            <div className="result-answers">
                                <h3>Answer Review</h3>
                                {currentResult.sections.map(section => (
                                    <div key={section.section_id} className="result-section">
                                        <h4>{section.section_title}</h4>
                                        <p className="section-score">
                                            Score: {section.marks_obtained}/{section.total_marks}
                                        </p>
                                        {section.questions.map((q, idx) => (
                                            <div key={q.question_id} className={`result-question ${q.is_correct ? 'correct' : 'incorrect'}`}>
                                                <div className="rq-header">
                                                    <span className="rq-number">Q{q.question_number || idx + 1}</span>
                                                    <span className={`rq-status ${q.is_correct ? 'correct' : 'incorrect'}`}>
                                                        {q.is_correct ? <CheckCircle size={16} /> : <XCircle size={16} />}
                                                        {q.is_correct ? 'Correct' : 'Incorrect'}
                                                    </span>
                                                    <span className="rq-marks">{q.marks_obtained}/{q.max_marks}</span>
                                                </div>
                                                <p className="rq-text">{q.question_text}</p>
                                                <div className="rq-answers">
                                                    <div className="rq-answer user">
                                                        <span className="rq-label">Your answer:</span>
                                                        <span className="rq-value">{q.user_answer || 'Not answered'}</span>
                                                    </div>
                                                    {!q.is_correct && (
                                                        <div className="rq-answer correct">
                                                            <span className="rq-label">Correct answer:</span>
                                                            <span className="rq-value">{q.correct_answer}</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className="result-modal-actions">
                            <button
                                className="btn-retake"
                                onClick={() => {
                                    setShowResultModal(false);
                                    navigate(`/test/assessment/${currentResult.assessment_id}`);
                                }}
                            >
                                <RotateCcw size={18} /> Take Again
                            </button>
                            <button
                                className="btn-dashboard"
                                onClick={() => {
                                    setShowResultModal(false);
                                    loadData();
                                    loadHistory();
                                }}
                            >
                                <Home size={18} /> Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

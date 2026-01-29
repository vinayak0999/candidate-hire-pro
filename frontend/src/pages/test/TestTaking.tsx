import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAntiCheat, useTestTimer } from '../../hooks/useAntiCheat';
import { API_BASE_URL, API_HOST, UPLOAD_BASE_URL } from '../../services/api';
import InPageBrowser from '../../components/InPageBrowser';
import './TestTaking.css';

// Helper to get full media URL
const getMediaUrl = (url?: string) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    return `${API_HOST}${url}`;
};

interface Question {
    id: number;
    question_type: string;
    question_text: string;
    options?: string[];
    media_url?: string;
    passage?: string;
    sentences?: string[];
    html_content?: string;
    documents?: Array<{ id: string; title: string; content: string }>;
    marks: number;
}

interface TestSession {
    attempt_id: number;
    test_id: number;
    test_title: string;
    duration_minutes: number;
    total_questions: number;
    questions: Question[];
    started_at: string;
    enable_tab_switch_detection: boolean;
    max_tab_switches_allowed: number;
}

export default function TestTaking() {
    const { testId } = useParams<{ testId: string }>();
    const navigate = useNavigate();

    const [session, setSession] = useState<TestSession | null>(null);
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    const [answers, setAnswers] = useState<Record<number, string>>({});
    const [flaggedQuestions, setFlaggedQuestions] = useState<Set<number>>(new Set());
    const [globalAnswerFile, setGlobalAnswerFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [showWarning, setShowWarning] = useState(false);
    const [warningMessage, setWarningMessage] = useState('');
    const [showSubmitModal, setShowSubmitModal] = useState(false);
    const [showQuestionNav, setShowQuestionNav] = useState(false);

    // Anti-cheat hook
    const isTabDetectionEnabled = session?.enable_tab_switch_detection === true;

    const antiCheat = useAntiCheat({
        onViolation: (type, count) => {
            if ((type === 'tab_switch' || type === 'window_blur') && !isTabDetectionEnabled) {
                return;
            }
            reportViolation(type);

            if (type === 'tab_switch' || type === 'window_blur') {
                const max = session?.max_tab_switches_allowed || 3;
                setWarningMessage(`Focus lost (${count}/${max}). Stay on this page.`);
                setShowWarning(true);
            } else if (type === 'fullscreen_exit') {
                setWarningMessage(`Fullscreen exit detected. Please stay in fullscreen mode.`);
                setShowWarning(true);
            } else if (type === 'devtools_open') {
                setWarningMessage(`Developer Tools detected! This has been flagged.`);
                setShowWarning(true);
            } else if (type === 'shortcut_blocked' || type === 'copy_attempt' || type === 'paste_attempt') {
                setWarningMessage(`This action is disabled during the test.`);
                setShowWarning(true);
            }
        },
        maxTabSwitches: session?.max_tab_switches_allowed || 3,
        maxFullscreenExits: 2,
        enableCopyProtection: true,
        enableFullscreenMode: true,
        enableTabDetection: isTabDetectionEnabled
    });

    // Timer
    const timer = useTestTimer(
        session?.duration_minutes || 60,
        () => handleSubmitTest(),
        session?.started_at
    );

    const getTimerUrgency = () => {
        if (timer.timeRemaining <= 60) return 'critical';
        if (timer.timeRemaining <= 120) return 'danger';
        if (timer.timeRemaining <= 300) return 'warning';
        return 'normal';
    };

    // Report violation
    const reportViolation = async (type: string) => {
        if (!session) return;
        try {
            const token = localStorage.getItem('access_token');
            if (!token) return;
            await fetch(`${API_BASE_URL}/tests/flag-violation/${session.attempt_id}?violation_type=${type}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
        } catch (error) {
            console.error('Failed to report violation:', error);
        }
    };

    // Start test
    useEffect(() => {
        const startTest = async () => {
            try {
                const token = localStorage.getItem('access_token');
                if (!token) { navigate('/login'); return; }

                const response = await fetch(`${API_BASE_URL}/tests/start`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({ test_id: parseInt(testId || '0') })
                });

                if (response.ok) {
                    const data = await response.json();
                    setSession(data);
                    timer.start();
                } else {
                    // Parse error message from backend
                    try {
                        const errorData = await response.json();
                        setError(errorData.detail || 'Failed to start test');
                    } catch {
                        setError('Failed to start test. Please try again.');
                    }
                    setLoading(false);
                }
            } catch (error) {
                console.error('Failed to start test:', error);
                setError('Network error. Please check your connection.');
                setLoading(false);
            } finally {
                setLoading(false);
            }
        };

        if (testId) startTest();
    }, [testId]);

    // Answer handling
    const handleSelectAnswer = useCallback((questionId: number, answer: string) => {
        setAnswers(prev => ({ ...prev, [questionId]: answer }));
    }, []);

    const toggleFlagQuestion = (questionId: number) => {
        setFlaggedQuestions(prev => {
            const newSet = new Set(prev);
            if (newSet.has(questionId)) newSet.delete(questionId);
            else newSet.add(questionId);
            return newSet;
        });
    };

    // Auto-save
    useEffect(() => {
        if (!session) return;
        const saveKey = `test_answers_${session.attempt_id}`;

        const localSaveInterval = setInterval(() => {
            localStorage.setItem(saveKey, JSON.stringify({
                answers,
                flaggedQuestions: Array.from(flaggedQuestions),
                savedAt: new Date().toISOString(),
                questionIndex: currentQuestionIndex
            }));
        }, 5000);

        const saved = localStorage.getItem(saveKey);
        if (saved) {
            try {
                const { answers: savedAnswers, flaggedQuestions: savedFlags } = JSON.parse(saved);
                if (savedAnswers && Object.keys(savedAnswers).length > 0) {
                    setAnswers(prev => ({ ...savedAnswers, ...prev }));
                }
                if (savedFlags?.length > 0) {
                    setFlaggedQuestions(new Set(savedFlags));
                }
            } catch (e) { /* ignore */ }
        }

        return () => clearInterval(localSaveInterval);
    }, [session, answers, currentQuestionIndex, flaggedQuestions]);

    // Backend sync
    useEffect(() => {
        if (!session) return;
        const token = localStorage.getItem('access_token');
        if (!token) return;

        const syncToBackend = async () => {
            for (const [questionId, answerText] of Object.entries(answers)) {
                try {
                    if (answerText.startsWith('FILE:')) continue;
                    await fetch(`${API_BASE_URL}/tests/submit-answer?attempt_id=${session.attempt_id}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                        body: JSON.stringify({ question_id: parseInt(questionId), answer_text: answerText })
                    });
                } catch (e) { /* retry next interval */ }
            }
        };

        const syncInterval = setInterval(syncToBackend, 30000);
        return () => clearInterval(syncInterval);
    }, [session, answers]);

    const goToQuestion = (index: number) => {
        if (index >= 0 && index < (session?.questions.length || 0)) {
            setCurrentQuestionIndex(index);
            setShowQuestionNav(false);
        }
    };

    // Submit
    const isSubmittedRef = useRef(false);

    const handleSubmitTest = async () => {
        if (!session || submitting || isSubmittedRef.current) return;

        isSubmittedRef.current = true;
        setSubmitting(true);
        setShowSubmitModal(false);

        try {
            const token = localStorage.getItem('access_token');
            if (!token) {
                alert('Session expired. Please login again.');
                isSubmittedRef.current = false;
                return;
            }

            if (globalAnswerFile) {
                try {
                    const firstAgentQ = session.questions.find(q => q.question_type === 'agent_analysis');
                    const questionId = firstAgentQ?.id || session.questions[0].id;

                    const formData = new FormData();
                    formData.append('file', globalAnswerFile);
                    formData.append('attempt_id', session.attempt_id.toString());
                    formData.append('question_id', questionId.toString());

                    const res = await fetch(`${UPLOAD_BASE_URL}/tests/upload-answer-file`, {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` },
                        body: formData
                    });

                    if (!res.ok) throw new Error('File upload failed');
                } catch (e) {
                    alert('Failed to upload your file. Please try again.');
                    isSubmittedRef.current = false;
                    setSubmitting(false);
                    return;
                }
            }

            const answerPromises = Object.entries(answers)
                .filter(([_, answerText]) => !answerText.startsWith('FILE:'))
                .map(async ([questionId, answerText]) => {
                    try {
                        await fetch(`${API_BASE_URL}/tests/submit-answer?attempt_id=${session.attempt_id}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                            body: JSON.stringify({ question_id: parseInt(questionId), answer_text: answerText })
                        });
                        return { questionId, success: true };
                    } catch (e) {
                        return { questionId, success: false };
                    }
                });

            await Promise.allSettled(answerPromises);

            const response = await fetch(`${API_BASE_URL}/tests/complete/${session.attempt_id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ attempt_id: session.attempt_id, tab_switches: antiCheat.tabSwitches })
            });

            if (response.ok) {
                const result = await response.json();
                antiCheat.exitFullscreen();
                localStorage.removeItem(`test_answers_${session.attempt_id}`);
                navigate(`/test-result/${session.attempt_id}`, { state: { result } });
            } else {
                throw new Error('Failed to complete test');
            }
        } catch (error) {
            alert(`Failed to submit test. Please try again.`);
        } finally {
            setSubmitting(false);
        }
    };

    // Stats
    const answeredCount = session ? Object.keys(answers).filter(id =>
        session.questions.some(q => q.id === parseInt(id) && answers[parseInt(id)]?.trim())
    ).length : 0;
    const flaggedCount = flaggedQuestions.size;

    // Precompute document URLs for fast rendering
    const currentQuestion = session?.questions[currentQuestionIndex];
    const processedDocs = useMemo(() => {
        if (!currentQuestion?.documents) return [];
        return currentQuestion.documents.map(d => {
            const isOffice = /\.(docx?|xlsx?|pptx?)$/i.test(d.content || '');
            let contentUrl = d.content;

            if (d.content?.startsWith('/')) {
                contentUrl = getMediaUrl(d.content);
            } else if (d.content?.startsWith('http')) {
                if (isOffice) {
                    contentUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(d.content)}`;
                } else {
                    contentUrl = `${API_BASE_URL}/tests/content-proxy?url=${encodeURIComponent(d.content)}`;
                }
            }
            return { id: d.id, title: d.title, content: contentUrl };
        });
    }, [currentQuestion?.documents]);

    const processedHtmlUrl = useMemo(() => {
        if (!currentQuestion?.html_content) return undefined;
        if (currentQuestion.html_content.startsWith('/')) {
            return getMediaUrl(currentQuestion.html_content);
        }
        if (currentQuestion.html_content.startsWith('http')) {
            return `${API_BASE_URL}/tests/content-proxy?url=${encodeURIComponent(currentQuestion.html_content)}`;
        }
        return undefined;
    }, [currentQuestion?.html_content]);

    if (loading) {
        return (
            <div className="test-loading">
                <div className="spinner"></div>
                <p>Preparing your assessment...</p>
            </div>
        );
    }

    // Show error message (e.g., "You have already completed this test")
    if (error) {
        const isAlreadyCompleted = error.toLowerCase().includes('already completed') || error.toLowerCase().includes('already taken');
        return (
            <div className="test-error">
                <div className="error-icon">
                    {isAlreadyCompleted ? '✅' : '⚠️'}
                </div>
                <h2>{isAlreadyCompleted ? 'Test Already Submitted' : 'Unable to Start Test'}</h2>
                <p>{error}</p>
                <div className="error-actions">
                    <button onClick={() => navigate('/opportunities')} className="btn-primary">
                        Back to Opportunities
                    </button>
                    {isAlreadyCompleted && (
                        <button onClick={() => navigate('/dashboard')} className="btn-secondary">
                            View Dashboard
                        </button>
                    )}
                </div>
            </div>
        );
    }

    if (!session || !session.questions?.length) {
        return (
            <div className="test-error">
                <h2>Unable to Load Test</h2>
                <p>Please try again or contact support.</p>
                <button onClick={() => navigate('/opportunities')}>Back to Opportunities</button>
            </div>
        );
    }

    return (
        <div className="test-taking-page">
            {/* Warning Modal */}
            {showWarning && (
                <div className="modal-overlay" onClick={() => setShowWarning(false)}>
                    <div className="warning-modal" onClick={e => e.stopPropagation()}>
                        <p>{warningMessage}</p>
                        <button onClick={() => setShowWarning(false)}>OK</button>
                    </div>
                </div>
            )}

            {/* Submit Modal */}
            {showSubmitModal && (
                <div className="modal-overlay">
                    <div className="submit-modal">
                        <h3>Submit Test?</h3>
                        <div className="submit-stats">
                            <div className="stat-item">
                                <span className="stat-value success">{answeredCount}</span>
                                <span className="stat-label">Answered</span>
                            </div>
                            <div className="stat-item">
                                <span className="stat-value error">{session.total_questions - answeredCount}</span>
                                <span className="stat-label">Unanswered</span>
                            </div>
                            {flaggedCount > 0 && (
                                <div className="stat-item">
                                    <span className="stat-value warning">{flaggedCount}</span>
                                    <span className="stat-label">Flagged</span>
                                </div>
                            )}
                        </div>
                        {session.total_questions - answeredCount > 0 && (
                            <p className="submit-warning">You have unanswered questions.</p>
                        )}
                        <div className="modal-actions">
                            <button className="btn-secondary" onClick={() => setShowSubmitModal(false)}>Review</button>
                            <button className="btn-primary" onClick={handleSubmitTest} disabled={submitting}>
                                {submitting ? 'Submitting...' : 'Submit'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Question Nav Popup */}
            {showQuestionNav && (
                <div className="modal-overlay" onClick={() => setShowQuestionNav(false)}>
                    <div className="question-nav-popup" onClick={e => e.stopPropagation()}>
                        <div className="nav-popup-header">
                            <h3>Questions</h3>
                            <button className="close-btn" onClick={() => setShowQuestionNav(false)}>×</button>
                        </div>
                        <div className="question-grid">
                            {session.questions.map((q, idx) => (
                                <button
                                    key={q.id}
                                    className={`q-btn ${idx === currentQuestionIndex ? 'current' : ''} ${answers[q.id]?.trim() ? 'answered' : ''} ${flaggedQuestions.has(q.id) ? 'flagged' : ''}`}
                                    onClick={() => goToQuestion(idx)}
                                >
                                    {idx + 1}
                                </button>
                            ))}
                        </div>
                        <div className="nav-legend">
                            <span><i className="dot current"></i> Current</span>
                            <span><i className="dot answered"></i> Answered</span>
                            <span><i className="dot flagged"></i> Flagged</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Header */}
            <header className="test-header">
                <div className="header-left">
                    <h1 className="test-title">{session.test_title}</h1>
                </div>

                <div className={`timer ${getTimerUrgency()}`}>
                    <span className="timer-icon">⏱</span>
                    <span className="timer-value">{timer.formattedTime}</span>
                </div>

                <div className="header-right">
                    <button className="nav-toggle" onClick={() => setShowQuestionNav(true)}>
                        <span>{currentQuestionIndex + 1}/{session.total_questions}</span>
                        <span className="toggle-icon">▼</span>
                    </button>
                    <button className="btn-submit" onClick={() => setShowSubmitModal(true)}>
                        Submit
                    </button>
                </div>
            </header>

            {/* Progress */}
            <div className="progress-track">
                <div className="progress-fill" style={{ width: `${(answeredCount / session.total_questions) * 100}%` }}></div>
            </div>

            {/* Flagged Banner */}
            {antiCheat.isFlagged && (
                <div className="flagged-banner">Test flagged for review</div>
            )}

            {/* Main Content - Full Width */}
            <main className="test-main">
                <div className="question-card">
                    {/* Question Header */}
                    <div className="q-header">
                        <div className="q-meta">
                            <span className="q-number">Q{currentQuestionIndex + 1}</span>
                            <span className={`q-type ${currentQuestion?.question_type}`}>
                                {currentQuestion?.question_type.replace(/_/g, ' ')}
                            </span>
                            <span className="q-marks">{currentQuestion?.marks} marks</span>
                        </div>
                        <button
                            className={`flag-btn ${flaggedQuestions.has(currentQuestion!.id) ? 'active' : ''}`}
                            onClick={() => toggleFlagQuestion(currentQuestion!.id)}
                        >
                            {flaggedQuestions.has(currentQuestion!.id) ? '🚩 Flagged' : '⚑ Flag'}
                        </button>
                    </div>

                    {/* Question Content */}
                    <div className="q-content" key={`content-${currentQuestion?.id}`}>
                        <p className="q-text">{currentQuestion?.question_text}</p>

                        {/* MCQ */}
                        {currentQuestion?.question_type === 'mcq' && currentQuestion.options && (
                            <div className="options">
                                {currentQuestion.options.map((opt, i) => (
                                    <label key={i} className={`option ${answers[currentQuestion.id] === opt ? 'selected' : ''}`}>
                                        <input
                                            type="radio"
                                            name={`q-${currentQuestion.id}`}
                                            checked={answers[currentQuestion.id] === opt}
                                            onChange={() => handleSelectAnswer(currentQuestion.id, opt)}
                                        />
                                        <span className="opt-letter">{String.fromCharCode(65 + i)}</span>
                                        <span className="opt-text">{opt}</span>
                                    </label>
                                ))}
                            </div>
                        )}

                        {/* Text */}
                        {(currentQuestion?.question_type === 'text_annotation' ||
                            currentQuestion?.question_type === 'text' ||
                            currentQuestion?.question_type === 'reading') && (
                                <textarea
                                    className="answer-textarea"
                                    placeholder="Type your answer..."
                                    value={answers[currentQuestion.id] || ''}
                                    onChange={(e) => handleSelectAnswer(currentQuestion.id, e.target.value)}
                                />
                            )}

                        {/* Image */}
                        {(currentQuestion?.question_type === 'image_annotation' ||
                            currentQuestion?.question_type === 'image') && (
                                <div className="media-answer">
                                    {currentQuestion.media_url && (
                                        <img src={getMediaUrl(currentQuestion.media_url)} alt="Question" />
                                    )}
                                    <textarea
                                        placeholder="Describe what you see..."
                                        value={answers[currentQuestion.id] || ''}
                                        onChange={(e) => handleSelectAnswer(currentQuestion.id, e.target.value)}
                                    />
                                </div>
                            )}

                        {/* Video */}
                        {(currentQuestion?.question_type === 'video_annotation' ||
                            currentQuestion?.question_type === 'video') && (
                                <div className="media-answer">
                                    {currentQuestion.media_url && (
                                        <video controls src={getMediaUrl(currentQuestion.media_url)} />
                                    )}
                                    <textarea
                                        placeholder="Describe what you observed..."
                                        value={answers[currentQuestion.id] || ''}
                                        onChange={(e) => handleSelectAnswer(currentQuestion.id, e.target.value)}
                                    />
                                </div>
                            )}

                        {/* Agent Analysis */}
                        {currentQuestion?.question_type === 'agent_analysis' && (
                            <div className="agent-area">
                                <InPageBrowser
                                    key={`browser-${currentQuestion.id}`}
                                    htmlUrl={processedHtmlUrl}
                                    htmlContent={
                                        currentQuestion.html_content?.startsWith('/') ||
                                            currentQuestion.html_content?.startsWith('http')
                                            ? undefined
                                            : currentQuestion.html_content || ''
                                    }
                                    documents={processedDocs}
                                />
                                <div className="file-upload">
                                    <p className="upload-label">Upload Final Report (Excel)</p>
                                    <input
                                        type="file"
                                        id="file-input"
                                        accept=".xlsx,.xls,.csv"
                                        onChange={(e) => e.target.files?.[0] && setGlobalAnswerFile(e.target.files[0])}
                                        hidden
                                    />
                                    <label htmlFor="file-input" className={`upload-zone ${globalAnswerFile ? 'has-file' : ''}`}>
                                        {globalAnswerFile ? `✓ ${globalAnswerFile.name}` : 'Click to upload .xlsx/.csv'}
                                    </label>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Navigation */}
                    <div className="q-nav">
                        <button
                            className="btn-nav"
                            onClick={() => goToQuestion(currentQuestionIndex - 1)}
                            disabled={currentQuestionIndex === 0}
                        >
                            ← Prev
                        </button>
                        <span className="q-indicator">{currentQuestionIndex + 1} / {session.total_questions}</span>
                        {currentQuestionIndex === session.questions.length - 1 ? (
                            <button className="btn-nav primary" onClick={() => setShowSubmitModal(true)}>
                                Submit →
                            </button>
                        ) : (
                            <button className="btn-nav primary" onClick={() => goToQuestion(currentQuestionIndex + 1)}>
                                Next →
                            </button>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}

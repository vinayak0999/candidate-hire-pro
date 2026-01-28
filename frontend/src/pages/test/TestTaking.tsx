import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAntiCheat, useTestTimer } from '../../hooks/useAntiCheat';
import { API_BASE_URL, API_HOST } from '../../services/api';
import InPageBrowser from '../../components/InPageBrowser';
import './TestTaking.css';

// Helper to get full media URL
const getMediaUrl = (url?: string) => {
    if (!url) return '';
    // If already a full URL (http/https or Cloudinary), return as-is
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    // Otherwise prepend backend host
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
    const [globalAnswerFile, setGlobalAnswerFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [showWarning, setShowWarning] = useState(false);
    const [warningMessage, setWarningMessage] = useState('');

    // Anti-cheat hook with 10K+ security
    const antiCheat = useAntiCheat({
        onViolation: (type, count) => {
            console.log(`Security Violation: ${type}, count: ${count}`);

            // Report ALL violations to backend
            reportViolation(type);

            if (type === 'tab_switch' || type === 'window_blur') {
                const max = session?.max_tab_switches_allowed || 3;
                setWarningMessage(`⚠️ Focus lost (${count}/${max}). Stay on this page.`);
                setShowWarning(true);
            } else if (type === 'fullscreen_exit') {
                setWarningMessage(`⚠️ Fullscreen exit detected. Please stay in fullscreen mode.`);
                setShowWarning(true);
            } else if (type === 'devtools_open') {
                setWarningMessage(`🚨 Developer Tools detected! This has been flagged.`);
                setShowWarning(true);
            } else if (type === 'shortcut_blocked') {
                setWarningMessage(`⚠️ Keyboard shortcuts are disabled during the test.`);
                setShowWarning(true);
            } else if (type === 'copy_attempt' || type === 'paste_attempt') {
                setWarningMessage(`⚠️ Copy/Paste is disabled during the test.`);
                setShowWarning(true);
            }
        },
        maxTabSwitches: session?.max_tab_switches_allowed || 3,
        maxFullscreenExits: 2,
        enableCopyProtection: true,
        enableFullscreenMode: true,
        enableTabDetection: session?.enable_tab_switch_detection ?? true
    });

    // Timer hook
    const timer = useTestTimer(
        session?.duration_minutes || 60,
        () => {
            // Auto-submit when time is up
            handleSubmitTest();
        },
        session?.started_at // Sync with server start time
    );

    // Report violation to backend
    const reportViolation = async (type: string) => {
        if (!session) return;
        try {
            const token = localStorage.getItem('access_token');
            // Check if token exists
            if (!token) return;

            await fetch(`${API_BASE_URL}/tests/flag-violation/${session.attempt_id}?violation_type=${type}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        } catch (error) {
            console.error('Failed to report violation:', error);
        }
    };

    // Start test session
    useEffect(() => {
        const startTest = async () => {
            try {
                const token = localStorage.getItem('access_token');
                if (!token) {
                    navigate('/login');
                    return;
                }

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
                    // Fullscreen removed - must be user-initiated per browser security policy
                } else {
                    console.error('Start test failed:', await response.text());
                    // navigate('/tests');
                    setLoading(false);
                }
            } catch (error) {
                console.error('Failed to start test:', error);
                // navigate('/tests');
                setLoading(false);
            } finally {
                setLoading(false);
            }
        };

        if (testId) {
            startTest();
        }
    }, [testId]);

    // Submit answer
    const handleSelectAnswer = useCallback((questionId: number, answer: string) => {
        setAnswers(prev => ({ ...prev, [questionId]: answer }));
    }, []);

    // Auto-save answers to localStorage (offline resilience)
    useEffect(() => {
        if (!session) return;
        const saveKey = `test_answers_${session.attempt_id}`;

        // Save to localStorage every 5 seconds
        const localSaveInterval = setInterval(() => {
            localStorage.setItem(saveKey, JSON.stringify({
                answers,
                savedAt: new Date().toISOString(),
                questionIndex: currentQuestionIndex
            }));
        }, 5000);

        // Restore saved answers on mount
        const saved = localStorage.getItem(saveKey);
        if (saved) {
            try {
                const { answers: savedAnswers } = JSON.parse(saved);
                if (savedAnswers && Object.keys(savedAnswers).length > 0) {
                    setAnswers(prev => ({ ...savedAnswers, ...prev }));
                }
            } catch (e) {
                console.warn('Failed to restore saved answers');
            }
        }

        return () => clearInterval(localSaveInterval);
    }, [session, answers, currentQuestionIndex]);

    // Sync answers to backend periodically (every 30s)
    useEffect(() => {
        if (!session) return;
        const token = localStorage.getItem('access_token');
        if (!token) return;

        const syncToBackend = async () => {
            for (const [questionId, answerText] of Object.entries(answers)) {
                try {
                    // Skip file placeholders
                    if (answerText.startsWith('FILE:')) continue;

                    await fetch(`${API_BASE_URL}/tests/submit-answer?attempt_id=${session.attempt_id}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${token}`
                        },
                        body: JSON.stringify({
                            question_id: parseInt(questionId),
                            answer_text: answerText
                        })
                    });
                } catch (e) {
                    console.warn('Auto-sync failed, will retry');
                }
            }
        };

        const syncInterval = setInterval(syncToBackend, 30000);
        return () => clearInterval(syncInterval);
    }, [session, answers]);

    // Navigate questions
    const goToQuestion = (index: number) => {
        if (index >= 0 && index < (session?.questions.length || 0)) {
            setCurrentQuestionIndex(index);
        }
    };

    // Submit test - with double-submit protection
    const isSubmittedRef = useRef(false);

    const handleSubmitTest = async () => {
        // Prevent double-submission
        if (!session || submitting || isSubmittedRef.current) {
            console.log('Submission blocked: already submitting or submitted');
            return;
        }

        isSubmittedRef.current = true; // Mark as submitted
        setSubmitting(true);

        try {
            const token = localStorage.getItem('access_token');
            if (!token) {
                alert('Session expired. Please login again.');
                isSubmittedRef.current = false;
                return;
            }

            // Upload global answer file (single file for all questions)
            if (globalAnswerFile) {
                try {
                    // Find first agent_analysis question ID for the file
                    const firstAgentQ = session.questions.find(q => q.question_type === 'agent_analysis');
                    const questionId = firstAgentQ?.id || session.questions[0].id;

                    const formData = new FormData();
                    formData.append('file', globalAnswerFile);
                    formData.append('attempt_id', session.attempt_id.toString());
                    formData.append('question_id', questionId.toString());

                    const res = await fetch(`${API_BASE_URL}/tests/upload-answer-file`, {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        },
                        body: formData
                    });

                    if (!res.ok) {
                        throw new Error('File upload failed');
                    }
                } catch (e) {
                    console.error('File upload failed', e);
                    alert('Failed to upload your Excel file. Please try again.');
                    isSubmittedRef.current = false;
                    setSubmitting(false);
                    return;
                }
            }

            // Submit all text answers IN PARALLEL for speed
            const answerPromises = Object.entries(answers)
                .filter(([_, answerText]) => !answerText.startsWith('FILE:'))
                .map(async ([questionId, answerText]) => {
                    try {
                        const res = await fetch(`${API_BASE_URL}/tests/submit-answer?attempt_id=${session.attempt_id}`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${token}`
                            },
                            body: JSON.stringify({
                                question_id: parseInt(questionId),
                                answer_text: answerText
                            })
                        });
                        if (!res.ok) throw new Error(`Q${questionId} failed`);
                        return { questionId, success: true };
                    } catch (e) {
                        console.error(`Failed to submit answer for question ${questionId}`, e);
                        return { questionId, success: false };
                    }
                });

            // Wait for all answers to submit (don't fail on individual errors)
            await Promise.allSettled(answerPromises);


            // Complete test
            const response = await fetch(`${API_BASE_URL}/tests/complete/${session.attempt_id}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    attempt_id: session.attempt_id,
                    tab_switches: antiCheat.tabSwitches
                })
            });

            if (response.ok) {
                const result = await response.json();
                antiCheat.exitFullscreen();
                navigate(`/test-result/${session.attempt_id}`, { state: { result } });
            } else {
                const errText = await response.text();
                throw new Error(errText || 'Failed to complete test');
            }
        } catch (error) {
            console.error('Failed to submit test:', error);
            alert(`Failed to submit test: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`);
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="test-loading">
                <div className="spinner"></div>
                <p>Loading test...</p>
            </div>
        );
    }

    if (!session) {
        return (
            <div className="test-error">
                <p>Failed to load test. Please try again.</p>
                <button onClick={() => navigate('/opportunities')}>Back to Opportunities</button>
            </div>
        );
    }

    // Handle empty questions case
    if (!session.questions || session.questions.length === 0) {
        return (
            <div className="test-error">
                <p>No questions available for this test.</p>
                <button onClick={() => navigate('/opportunities')}>Back to Opportunities</button>
            </div>
        );
    }

    const currentQuestion = session.questions[currentQuestionIndex];
    if (!currentQuestion) {
        return (
            <div className="test-error">
                <p>Question not found.</p>
                <button onClick={() => navigate('/opportunities')}>Back to Opportunities</button>
            </div>
        );
    }
    // const answeredCount = Object.keys(answers).length;
    // const progress = (answeredCount / session.total_questions) * 100;

    return (
        <div className="test-taking-page">
            {/* Warning Modal */}
            {showWarning && (
                <div className="warning-overlay">
                    <div className="warning-modal">
                        <div className="warning-icon">⚠️</div>
                        <p>{warningMessage}</p>
                        <button onClick={() => setShowWarning(false)}>I Understand</button>
                    </div>
                </div>
            )}

            {/* Header */}
            <header className="test-header">
                <div className="test-info">
                    <h1>{session.test_title}</h1>
                    <span className="question-counter">
                        Question {currentQuestionIndex + 1} of {session.total_questions}
                    </span>
                </div>

                {/* Question nav grid removed - redundant with Question X of Y */}

                <div className="test-timer" data-urgent={timer.timeRemaining < 300}>
                    <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z" />
                    </svg>
                    <span>{timer.formattedTime}</span>
                </div>
            </header>

            {/* Progress Bar removed as per request */}

            {/* Anti-cheat status */}
            {antiCheat.isFlagged && (
                <div className="flagged-banner">
                    ⚠️ Your test has been flagged for review due to suspicious activity
                </div>
            )}

            {/* Main Content */}
            <div className="test-content">
                {/* Sidebar Removed */}

                {/* Question Display - All questions mounted, only active visible (for instant switching) */}
                <main className="question-area">
                    {session.questions.map((question, qIndex) => (
                        <div
                            key={question.id}
                            className="question-card"
                            style={{ display: qIndex === currentQuestionIndex ? 'block' : 'none' }}
                        >
                            <div className="question-header">
                                <span className="question-type">{question.question_type.toUpperCase()}</span>
                                <span className="question-marks">{question.marks} marks</span>
                            </div>

                            <div className="question-text">
                                {question.question_text}
                            </div>

                            {/* MCQ Options */}
                            {question.question_type === 'mcq' && question.options && (
                                <div className="options-list">
                                    {question.options.map((option, idx) => (
                                        <label
                                            key={idx}
                                            className={`option-item ${answers[question.id] === option ? 'selected' : ''}`}
                                        >
                                            <input
                                                type="radio"
                                                name={`question-${question.id}`}
                                                value={option}
                                                checked={answers[question.id] === option}
                                                onChange={() => handleSelectAnswer(question.id, option)}
                                            />
                                            <span className="option-letter">{String.fromCharCode(65 + idx)}</span>
                                            <span className="option-text">{option}</span>
                                        </label>
                                    ))}
                                </div>
                            )}

                            {/* Text Annotation */}
                            {(question.question_type === 'text_annotation' || question.question_type === 'text' || question.question_type === 'reading') && (
                                <div className="text-annotation-area">
                                    <textarea
                                        placeholder="Enter your annotation..."
                                        value={answers[question.id] || ''}
                                        onChange={(e) => handleSelectAnswer(question.id, e.target.value)}
                                        rows={6}
                                    />
                                </div>
                            )}

                            {/* Image Annotation */}
                            {(question.question_type === 'image_annotation' || question.question_type === 'image') && (
                                <div className="image-annotation-area">
                                    {question.media_url && (
                                        <img src={getMediaUrl(question.media_url)} alt="Annotation target" />
                                    )}
                                    <textarea
                                        placeholder="Describe what you see in the image..."
                                        value={answers[question.id] || ''}
                                        onChange={(e) => handleSelectAnswer(question.id, e.target.value)}
                                        rows={4}
                                    />
                                </div>
                            )}

                            {/* Video Annotation */}
                            {(question.question_type === 'video_annotation' || question.question_type === 'video') && (
                                <div className="video-annotation-area">
                                    {question.media_url && (
                                        <video controls>
                                            <source src={getMediaUrl(question.media_url)} type="video/mp4" />
                                            Your browser does not support video playback.
                                        </video>
                                    )}
                                    <textarea
                                        placeholder="Describe what you observed in the video..."
                                        value={answers[question.id] || ''}
                                        onChange={(e) => handleSelectAnswer(question.id, e.target.value)}
                                        rows={4}
                                    />
                                </div>
                            )}

                            {/* Agent Analysis */}
                            {question.question_type === 'agent_analysis' && (
                                <div className="agent-analysis-area">
                                    <InPageBrowser
                                        htmlUrl={
                                            question.html_content?.startsWith('/') ||
                                                question.html_content?.startsWith('http')
                                                ? (question.html_content.startsWith('/')
                                                    ? getMediaUrl(question.html_content)
                                                    : `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api'}/tests/content-proxy?url=${encodeURIComponent(question.html_content)}`)
                                                : undefined
                                        }
                                        htmlContent={
                                            question.html_content?.startsWith('/') ||
                                                question.html_content?.startsWith('http')
                                                ? undefined
                                                : question.html_content || ''
                                        }
                                        documents={(question.documents || []).map(d => {
                                            const isOffice = /\.(docx?|xlsx?|pptx?)$/i.test(d.content || '');
                                            let contentUrl = d.content;

                                            if (d.content?.startsWith('/')) {
                                                contentUrl = getMediaUrl(d.content);
                                            } else if (d.content?.startsWith('http')) {
                                                if (isOffice) {
                                                    contentUrl = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(d.content)}`;
                                                } else {
                                                    contentUrl = `${import.meta.env.VITE_API_URL || 'http://localhost:8000/api'}/tests/content-proxy?url=${encodeURIComponent(d.content)}`;
                                                }
                                            }

                                            return {
                                                id: d.id,
                                                title: d.title,
                                                content: contentUrl
                                            };
                                        })}
                                    />
                                    <div className="agent-answer-section">
                                        <label>Upload Your Final Report</label>
                                        <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '12px' }}>
                                            Submit ONE Excel file with all your answers for all questions
                                        </p>
                                        <div className="file-upload-area">
                                            <input
                                                type="file"
                                                id="global-file-upload"
                                                accept=".xlsx,.xls,.csv"
                                                onChange={(e) => {
                                                    const file = e.target.files?.[0];
                                                    if (file) {
                                                        setGlobalAnswerFile(file);
                                                    }
                                                }}
                                                style={{ display: 'none' }}
                                            />
                                            <label
                                                htmlFor="global-file-upload"
                                                className="file-upload-label"
                                                style={{
                                                    display: 'flex',
                                                    flexDirection: 'column',
                                                    alignItems: 'center',
                                                    padding: '24px',
                                                    border: globalAnswerFile ? '2px solid #22c55e' : '2px dashed #e2e8f0',
                                                    borderRadius: '12px',
                                                    cursor: 'pointer',
                                                    background: globalAnswerFile ? '#f0fdf4' : '#f8fafc',
                                                    transition: 'all 0.2s'
                                                }}
                                            >
                                                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={globalAnswerFile ? '#22c55e' : '#64748b'} strokeWidth="1.5">
                                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                                    <polyline points="17 8 12 3 7 8" />
                                                    <line x1="12" y1="3" x2="12" y2="15" />
                                                </svg>
                                                <span style={{ marginTop: '8px', fontWeight: 600, color: globalAnswerFile ? '#16a34a' : '#1e293b' }}>
                                                    {globalAnswerFile
                                                        ? `✅ ${globalAnswerFile.name}`
                                                        : 'Click to upload Excel file'}
                                                </span>
                                                <span style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                                                    Supports .xlsx, .xls, .csv
                                                </span>
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}

                    {/* Navigation Buttons */}
                    <div className="question-actions">
                        <button
                            className="btn-secondary"
                            onClick={() => goToQuestion(currentQuestionIndex - 1)}
                            disabled={currentQuestionIndex === 0}
                        >
                            ← Previous
                        </button>

                        {currentQuestionIndex === session.questions.length - 1 ? (
                            <button
                                className="btn-submit"
                                onClick={handleSubmitTest}
                                disabled={submitting}
                            >
                                {submitting ? 'Submitting...' : 'Submit Test'}
                            </button>
                        ) : (
                            <button
                                className="btn-primary"
                                onClick={() => goToQuestion(currentQuestionIndex + 1)}
                            >
                                Next →
                            </button>
                        )}
                    </div>
                </main>
            </div>
        </div>
    );
}

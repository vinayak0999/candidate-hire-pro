import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { API_BASE_URL } from '../../services/api';
import './TestResult.css';

interface TestResult {
    attempt_id: number;
    test_id: number;
    test_title: string;
    score: number;
    total_marks: number;
    percentage: number;
    passed: boolean;
    time_taken_seconds: number;
    completed_at: string;
    answers: Array<{
        question_id: number;
        question_text: string;
        user_answer: string | null;
        correct_answer: string | null;
        is_correct: boolean | null;
        marks_obtained: number;
        max_marks: number;
    }>;
}

export default function TestResult() {
    const location = useLocation();
    const navigate = useNavigate();
    const { attemptId } = useParams<{ attemptId: string }>();
    const [result, setResult] = useState<TestResult | null>(location.state?.result || null);
    const [loading, setLoading] = useState(!location.state?.result);

    useEffect(() => {
        if (!result && attemptId) {
            fetchResult();
        }
    }, [attemptId]);

    const fetchResult = async () => {
        try {
            const token = localStorage.getItem('access_token');

            // Try regular test result first
            let response = await fetch(`${API_BASE_URL}/tests/result/${attemptId}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                setResult(data);
                return;
            }

            // If not found, try standalone assessment result
            response = await fetch(`${API_BASE_URL}/standalone-assessments/candidate/results/${attemptId}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                // Flatten sections into answers array for consistent display
                const flatAnswers: TestResult['answers'] = [];
                if (data.sections) {
                    for (const section of data.sections) {
                        for (const q of section.questions || []) {
                            flatAnswers.push({
                                question_id: q.question_id,
                                question_text: q.question_text,
                                user_answer: q.user_answer,
                                correct_answer: q.correct_answer,
                                is_correct: q.is_correct,
                                marks_obtained: q.marks_obtained,
                                max_marks: q.max_marks,
                            });
                        }
                    }
                }
                setResult({
                    attempt_id: data.attempt_id,
                    test_id: data.assessment_id,
                    test_title: data.assessment_title,
                    score: data.score,
                    total_marks: data.total_marks,
                    percentage: data.percentage,
                    passed: data.passed,
                    time_taken_seconds: data.time_taken_seconds,
                    completed_at: data.completed_at,
                    answers: flatAnswers,
                });
            }
        } catch (error) {
            console.error('Failed to fetch result:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}m ${secs}s`;
    };

    if (loading) {
        return (
            <div className="result-loading">
                <div className="spinner"></div>
                <p>Loading results...</p>
            </div>
        );
    }

    if (!result) {
        return (
            <div className="result-error">
                <p>Result not found</p>
                <button onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
            </div>
        );
    }

    const correctAnswers = result.answers.filter(a => a.is_correct).length;
    const incorrectAnswers = result.answers.filter(a => a.is_correct === false).length;

    // Check if any answer is submitted but not graded (is_correct is null/undefined)
    const hasPending = result.answers.some(a => a.user_answer && a.is_correct === null);

    return (
        <div className="test-result-page">
            {/* Header */}
            <header className="result-header">
                <button className="back-btn" onClick={() => navigate('/dashboard')}>
                    ← Back to Dashboard
                </button>
            </header>

            {/* Result Card */}
            <div className="result-container">
                <div className={`result-card ${result.passed ? 'passed' : hasPending ? 'pending-eval' : 'failed'}`}>
                    <div className="result-icon">
                        {result.passed ? '🎉' : hasPending ? '📨' : '📝'}
                    </div>
                    <h1>{result.passed ? 'Congratulations!' : hasPending ? 'Thank You!' : 'Test Completed'}</h1>
                    <p style={{ marginTop: '8px', color: '#64748b' }}>Your test has been successfully submitted.</p>
                    <p className="result-test-title">{result.test_title}</p>

                    {!hasPending ? (
                        <>
                            <div className="score-circle">
                                <svg viewBox="0 0 36 36" className="circular-chart">
                                    <path
                                        className="circle-bg"
                                        d="M18 2.0845
                                            a 15.9155 15.9155 0 0 1 0 31.831
                                            a 15.9155 15.9155 0 0 1 0 -31.831"
                                    />
                                    <path
                                        className="circle"
                                        strokeDasharray={`${result.percentage}, 100`}
                                        d="M18 2.0845
                                            a 15.9155 15.9155 0 0 1 0 31.831
                                            a 15.9155 15.9155 0 0 1 0 -31.831"
                                    />
                                </svg>
                                <div className="score-text">
                                    <span className="percentage">{Math.round(result.percentage)}%</span>
                                    <span className="label">Score</span>
                                </div>
                            </div>

                            <div className="result-stats">
                                <div className="stat">
                                    <span className="stat-value">{result.score}/{result.total_marks}</span>
                                    <span className="stat-label">Marks</span>
                                </div>
                                <div className="stat">
                                    <span className="stat-value">{formatTime(result.time_taken_seconds)}</span>
                                    <span className="stat-label">Time Taken</span>
                                </div>
                                <div className="stat">
                                    <span className="stat-value correct">{correctAnswers}</span>
                                    <span className="stat-label">Correct</span>
                                </div>
                                <div className="stat">
                                    <span className="stat-value incorrect">{incorrectAnswers}</span>
                                    <span className="stat-label">Incorrect</span>
                                </div>
                            </div>

                            <div className={`result-badge ${result.passed ? 'pass' : 'fail'}`}>
                                {result.passed ? '✓ PASSED' : '✗ NOT PASSED'}
                            </div>
                        </>
                    ) : (
                        <div className="pending-notice" style={{ padding: '20px', textAlign: 'center', background: '#f8fafc', borderRadius: '8px', margin: '20px 0' }}>
                            <h3 style={{ marginBottom: '8px', color: '#334155' }}>Evaluation In Progress</h3>
                            <p style={{ color: '#64748b' }}>
                                Your responses have been recorded. Our team will review your submission shortly.
                            </p>
                        </div>
                    )}
                </div>

                {/* Answer Review */}
                <div className="answer-review">
                    <h2>Answer Review</h2>
                    <div className="answers-list">
                        {result.answers.map((answer, idx) => {
                            let statusLabel = '— Not Answered';
                            let statusClass = 'unanswered';

                            if (answer.is_correct === true) {
                                statusLabel = '✓ Correct';
                                statusClass = 'correct';
                            } else if (answer.is_correct === false) {
                                statusLabel = '✗ Incorrect';
                                statusClass = 'incorrect';
                            } else if (answer.user_answer) {
                                statusLabel = '⏳ Pending Review';
                                statusClass = 'pending'; // You may need CSS for this or rely on default
                            }

                            return (
                                <div
                                    key={answer.question_id}
                                    className={`answer-item ${statusClass}`}
                                >
                                    <div className="answer-header">
                                        <span className="question-number">Q{idx + 1}</span>
                                        <span className={`answer-status ${statusClass}`} style={statusClass === 'pending' ? { color: '#ca8a04', background: '#fefce8' } : {}}>
                                            {statusLabel}
                                        </span>
                                        <span className="answer-marks">{answer.marks_obtained}/{answer.max_marks}</span>
                                    </div>
                                    <p className="question-text">{answer.question_text}</p>
                                    <div className="answer-details">
                                        <div className="your-answer">
                                            <strong>Your answer:</strong>
                                            {answer.user_answer?.startsWith('FILE:') ? (
                                                <a
                                                    href={answer.user_answer.replace('FILE:', '')}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="file-link"
                                                    style={{ color: '#2563eb', textDecoration: 'underline', marginLeft: '4px' }}
                                                >
                                                    Download Answer File
                                                </a>
                                            ) : (
                                                answer.user_answer || '(No answer)'
                                            )}
                                        </div>
                                        {answer.correct_answer && (
                                            <div className="correct-answer">
                                                <strong>Correct answer:</strong> {answer.correct_answer}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Actions */}
                <div className="result-actions">
                    <button className="btn-secondary" onClick={() => navigate('/tests')}>
                        Take Another Test
                    </button>
                    <button className="btn-primary" onClick={() => navigate('/dashboard')}>
                        Go to Dashboard
                    </button>
                </div>
            </div>
        </div>
    );
}

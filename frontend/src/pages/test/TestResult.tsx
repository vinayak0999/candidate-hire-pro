import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
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
            const token = localStorage.getItem('token');
            const response = await fetch(`http://localhost:8000/api/tests/result/${attemptId}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                setResult(data);
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
                <div className={`result-card ${result.passed ? 'passed' : 'failed'}`}>
                    <div className="result-icon">
                        {result.passed ? '🎉' : '📝'}
                    </div>
                    <h1>{result.passed ? 'Congratulations!' : 'Test Completed'}</h1>
                    <p className="result-test-title">{result.test_title}</p>

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
                </div>

                {/* Answer Review */}
                <div className="answer-review">
                    <h2>Answer Review</h2>
                    <div className="answers-list">
                        {result.answers.map((answer, idx) => (
                            <div
                                key={answer.question_id}
                                className={`answer-item ${answer.is_correct === true ? 'correct' : answer.is_correct === false ? 'incorrect' : 'unanswered'}`}
                            >
                                <div className="answer-header">
                                    <span className="question-number">Q{idx + 1}</span>
                                    <span className={`answer-status ${answer.is_correct === true ? 'correct' : answer.is_correct === false ? 'incorrect' : 'unanswered'}`}>
                                        {answer.is_correct === true ? '✓ Correct' : answer.is_correct === false ? '✗ Incorrect' : '— Not Answered'}
                                    </span>
                                    <span className="answer-marks">{answer.marks_obtained}/{answer.max_marks}</span>
                                </div>
                                <p className="question-text">{answer.question_text}</p>
                                <div className="answer-details">
                                    <div className="your-answer">
                                        <strong>Your answer:</strong> {answer.user_answer || '(No answer)'}
                                    </div>
                                    {answer.correct_answer && (
                                        <div className="correct-answer">
                                            <strong>Correct answer:</strong> {answer.correct_answer}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
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

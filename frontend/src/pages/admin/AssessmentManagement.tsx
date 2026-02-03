import { useState, useEffect, useCallback, memo, useMemo } from 'react';
import {
    Plus, Trash2, ChevronDown, ChevronRight, X, Eye, Wand2, ClipboardList,
    Library, FileText, Clock, Award, CheckSquare, Edit2, Save, BookOpen, Brain, BarChart2, CheckCircle, XCircle, User
} from 'lucide-react';
import './AssessmentManagement.css';

// ===== API Configuration =====
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function apiRequest(endpoint: string, options: RequestInit = {}) {
    const token = localStorage.getItem('admin_token') || localStorage.getItem('access_token');
    const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...options.headers,
        },
    });
    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || 'Request failed');
    }
    return res.json();
}

// ===== TYPES =====
interface Assessment {
    id: number;
    title: string;
    description: string | null;
    category: string | null;
    duration_minutes: number;
    total_questions: number;
    total_marks: number;
    passing_marks: number;
    is_published: boolean;
    is_active: boolean;
    created_at: string;
    sections: Section[];
}

interface Section {
    id: number;
    test_id: number;
    title: string;
    instructions: string | null;
    total_marks: number;
    order: number;
    passage: string | null;
    questions: Question[];
    created_at: string;
}

interface Question {
    id: number;
    section_id: number;
    question_number: string | null;
    question_type: string;
    question_text: string;
    options: Array<{ id: string; text: string }> | null;
    correct_answer: string | null;
    passage_id: string | null;
    marks: number;
    difficulty: string;
    is_active: boolean;
    created_at: string;
}

// ===== CONSTANTS =====
const CATEGORIES = ['English', 'Logical', 'Technical', 'Aptitude', 'Verbal', 'Other'];

const DIFFICULTY_COLORS: Record<string, { bg: string; text: string }> = {
    easy: { bg: '#dcfce7', text: '#16a34a' },
    medium: { bg: '#fef3c7', text: '#d97706' },
    hard: { bg: '#fee2e2', text: '#dc2626' },
};

type TabType = 'assessments' | 'editor' | 'results';

// ===== QUESTION CARD =====
const QuestionCard = memo(({
    question,
    onEdit,
    onDelete
}: {
    question: Question;
    onEdit: (q: Question) => void;
    onDelete: (id: number) => void;
}) => {
    const [expanded, setExpanded] = useState(false);
    const diffStyle = DIFFICULTY_COLORS[question.difficulty] || DIFFICULTY_COLORS.medium;

    return (
        <div className={`question-card ${expanded ? 'expanded' : ''}`}>
            <div className="question-card-header" onClick={() => setExpanded(!expanded)}>
                <div className="question-number-badge">
                    Q{question.question_number || question.id}
                </div>
                <span className="difficulty-pill" style={{ background: diffStyle.bg, color: diffStyle.text }}>
                    {question.difficulty}
                </span>
                <span className="marks-badge">{question.marks} mark{question.marks !== 1 ? 's' : ''}</span>
                <div className="question-card-actions">
                    <button className="icon-btn" onClick={(e) => { e.stopPropagation(); onEdit(question); }} title="Edit">
                        <Edit2 size={16} />
                    </button>
                    <button className="icon-btn danger" onClick={(e) => { e.stopPropagation(); onDelete(question.id); }}>
                        <Trash2 size={16} />
                    </button>
                    {expanded ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                </div>
            </div>
            <p className="question-text">{question.question_text}</p>
            {expanded && question.options && (
                <div className="question-preview-panel">
                    <div className="preview-block">
                        <label>Options</label>
                        <div className="options-grid">
                            {question.options.map((opt) => (
                                <div key={opt.id} className={`option-chip ${opt.id === question.correct_answer ? 'correct' : ''}`}>
                                    <span className="option-letter">{opt.id}</span>
                                    <span>{opt.text}</span>
                                    {opt.id === question.correct_answer && <CheckSquare size={14} className="check-icon" />}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
});

// ===== SECTION CARD =====
const SectionCard = memo(({
    section,
    onAddQuestion,
    onEditQuestion,
    onDeleteQuestion,
    onEditSection,
    onDeleteSection
}: {
    section: Section;
    onAddQuestion: (sectionId: number) => void;
    onEditQuestion: (q: Question) => void;
    onDeleteQuestion: (id: number) => void;
    onEditSection: (s: Section) => void;
    onDeleteSection: (id: number) => void;
}) => {
    const [expanded, setExpanded] = useState(true);

    return (
        <div className="section-card">
            <div className="section-header" onClick={() => setExpanded(!expanded)}>
                <div className="section-title">
                    <div className="section-icon">
                        <BookOpen size={18} />
                    </div>
                    <span>{section.title}</span>
                    <span className="section-stats">
                        {section.questions.length} questions • {section.total_marks} marks
                    </span>
                </div>
                <div className="section-actions">
                    <button className="icon-btn" onClick={(e) => { e.stopPropagation(); onEditSection(section); }} title="Edit Section">
                        <Edit2 size={16} />
                    </button>
                    <button className="icon-btn danger" onClick={(e) => { e.stopPropagation(); onDeleteSection(section.id); }} title="Delete Section">
                        <Trash2 size={16} />
                    </button>
                    {expanded ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                </div>
            </div>

            {expanded && (
                <div className="section-body">
                    {section.instructions && (
                        <p className="section-instructions">{section.instructions}</p>
                    )}
                    {section.passage && (
                        <div className="section-passage">
                            <label>Passage:</label>
                            <p>{section.passage.substring(0, 200)}...</p>
                        </div>
                    )}

                    <div className="questions-list">
                        {section.questions.length === 0 ? (
                            <p className="empty-text">No questions yet. Add one below.</p>
                        ) : (
                            section.questions.map(q => (
                                <QuestionCard
                                    key={q.id}
                                    question={q}
                                    onEdit={onEditQuestion}
                                    onDelete={onDeleteQuestion}
                                />
                            ))
                        )}
                    </div>

                    <button className="btn-add-question" onClick={() => onAddQuestion(section.id)}>
                        <Plus size={16} /> Add Question
                    </button>
                </div>
            )}
        </div>
    );
});

// ===== MAIN COMPONENT =====
export default function AssessmentManagement() {
    const [activeTab, setActiveTab] = useState<TabType>('assessments');
    const [assessments, setAssessments] = useState<Assessment[]>([]);
    const [selectedAssessment, setSelectedAssessment] = useState<Assessment | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [results, setResults] = useState<any[]>([]);

    // Modal states
    const [showAssessmentModal, setShowAssessmentModal] = useState(false);
    const [showSectionModal, setShowSectionModal] = useState(false);
    const [showQuestionModal, setShowQuestionModal] = useState(false);
    const [deleteModal, setDeleteModal] = useState<{ open: boolean; type: string; id: number | null; name: string }>({
        open: false, type: '', id: null, name: ''
    });

    // Form states
    const [assessmentForm, setAssessmentForm] = useState({
        id: null as number | null,
        title: '',
        description: '',
        category: 'English',
        duration_minutes: 60,
        total_questions: 0,
        total_marks: 0,
        passing_marks: 0,
    });

    const [sectionForm, setSectionForm] = useState({
        id: null as number | null,
        title: '',
        instructions: '',
        order: 1,
        passage: '',
    });

    const [questionForm, setQuestionForm] = useState({
        id: null as number | null,
        section_id: null as number | null,
        question_number: '',
        question_text: '',
        options: [
            { id: 'i', text: '' },
            { id: 'ii', text: '' },
            { id: 'iii', text: '' },
            { id: 'iv', text: '' },
        ],
        correct_answer: '',
        marks: 1,
        difficulty: 'medium',
    });

    // ===== DATA FETCHING =====
    const loadAssessments = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await apiRequest('/standalone-assessments');
            setAssessments(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    const loadAssessment = useCallback(async (id: number) => {
        setLoading(true);
        try {
            const data = await apiRequest(`/standalone-assessments/${id}`);
            setSelectedAssessment(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadAssessments();
    }, [loadAssessments]);

    const loadResults = useCallback(async () => {
        try {
            const data = await apiRequest('/standalone-assessments/admin/results');
            setResults(data);
        } catch (err: any) {
            console.error('Failed to load results:', err);
        }
    }, []);

    useEffect(() => {
        if (activeTab === 'results' && results.length === 0) {
            loadResults();
        }
    }, [activeTab, results.length, loadResults]);

    // ===== ASSESSMENT CRUD =====
    const handleSaveAssessment = async () => {
        try {
            if (assessmentForm.id) {
                await apiRequest(`/standalone-assessments/${assessmentForm.id}`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        title: assessmentForm.title,
                        description: assessmentForm.description,
                        category: assessmentForm.category,
                        duration_minutes: assessmentForm.duration_minutes,
                        total_questions: assessmentForm.total_questions,
                        total_marks: assessmentForm.total_marks,
                        passing_marks: assessmentForm.passing_marks,
                    }),
                });
            } else {
                await apiRequest('/standalone-assessments', {
                    method: 'POST',
                    body: JSON.stringify({
                        title: assessmentForm.title,
                        description: assessmentForm.description,
                        category: assessmentForm.category,
                        duration_minutes: assessmentForm.duration_minutes,
                        passing_marks: assessmentForm.passing_marks,
                    }),
                });
            }
            setShowAssessmentModal(false);
            resetAssessmentForm();
            loadAssessments();
        } catch (err: any) {
            alert(err.message);
        }
    };

    const handlePublish = async (id: number) => {
        try {
            await apiRequest(`/standalone-assessments/${id}/publish`, { method: 'POST' });
            loadAssessments();
            if (selectedAssessment?.id === id) {
                loadAssessment(id);
            }
        } catch (err: any) {
            alert(err.message);
        }
    };

    const handleUnpublish = async (id: number) => {
        try {
            await apiRequest(`/standalone-assessments/${id}/unpublish`, { method: 'POST' });
            loadAssessments();
            if (selectedAssessment?.id === id) {
                loadAssessment(id);
            }
        } catch (err: any) {
            alert(err.message);
        }
    };

    // ===== SECTION CRUD =====
    const handleSaveSection = async () => {
        if (!selectedAssessment) return;
        try {
            if (sectionForm.id) {
                await apiRequest(`/standalone-assessments/sections/${sectionForm.id}`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        title: sectionForm.title,
                        instructions: sectionForm.instructions || null,
                        order: sectionForm.order,
                        passage: sectionForm.passage || null,
                    }),
                });
            } else {
                await apiRequest(`/standalone-assessments/${selectedAssessment.id}/sections`, {
                    method: 'POST',
                    body: JSON.stringify({
                        title: sectionForm.title,
                        instructions: sectionForm.instructions || null,
                        order: sectionForm.order,
                        passage: sectionForm.passage || null,
                    }),
                });
            }
            setShowSectionModal(false);
            resetSectionForm();
            loadAssessment(selectedAssessment.id);
        } catch (err: any) {
            alert(err.message);
        }
    };

    // ===== QUESTION CRUD =====
    const handleSaveQuestion = async () => {
        if (!questionForm.section_id) return;
        try {
            const payload = {
                question_number: questionForm.question_number || null,
                question_type: 'mcq',
                question_text: questionForm.question_text,
                options: questionForm.options.filter(o => o.text.trim()),
                correct_answer: questionForm.correct_answer,
                marks: questionForm.marks,
                difficulty: questionForm.difficulty,
            };

            if (questionForm.id) {
                await apiRequest(`/standalone-assessments/questions/${questionForm.id}`, {
                    method: 'PUT',
                    body: JSON.stringify(payload),
                });
            } else {
                await apiRequest(`/standalone-assessments/sections/${questionForm.section_id}/questions`, {
                    method: 'POST',
                    body: JSON.stringify(payload),
                });
            }
            setShowQuestionModal(false);
            resetQuestionForm();
            if (selectedAssessment) {
                loadAssessment(selectedAssessment.id);
            }
        } catch (err: any) {
            alert(err.message);
        }
    };

    // ===== DELETE HANDLERS =====
    const confirmDelete = async () => {
        if (!deleteModal.id) return;
        try {
            if (deleteModal.type === 'assessment') {
                await apiRequest(`/standalone-assessments/${deleteModal.id}`, { method: 'DELETE' });
                loadAssessments();
                if (selectedAssessment?.id === deleteModal.id) {
                    setSelectedAssessment(null);
                    setActiveTab('assessments');
                }
            } else if (deleteModal.type === 'section') {
                await apiRequest(`/standalone-assessments/sections/${deleteModal.id}`, { method: 'DELETE' });
                if (selectedAssessment) loadAssessment(selectedAssessment.id);
            } else if (deleteModal.type === 'question') {
                await apiRequest(`/standalone-assessments/questions/${deleteModal.id}`, { method: 'DELETE' });
                if (selectedAssessment) loadAssessment(selectedAssessment.id);
            }
        } catch (err: any) {
            alert(err.message);
        }
        setDeleteModal({ open: false, type: '', id: null, name: '' });
    };

    // ===== FORM RESETS =====
    const resetAssessmentForm = () => {
        setAssessmentForm({
            id: null, title: '', description: '', category: 'English',
            duration_minutes: 60, total_questions: 0, total_marks: 0, passing_marks: 0,
        });
    };

    const resetSectionForm = () => {
        setSectionForm({ id: null, title: '', instructions: '', order: 1, passage: '' });
    };

    const resetQuestionForm = () => {
        setQuestionForm({
            id: null, section_id: null, question_number: '', question_text: '',
            options: [{ id: 'i', text: '' }, { id: 'ii', text: '' }, { id: 'iii', text: '' }, { id: 'iv', text: '' }],
            correct_answer: '', marks: 1, difficulty: 'medium',
        });
    };

    // ===== EDIT HANDLERS =====
    const handleEditAssessment = (a: Assessment) => {
        setAssessmentForm({
            id: a.id,
            title: a.title,
            description: a.description || '',
            category: a.category || 'English',
            duration_minutes: a.duration_minutes,
            total_questions: a.total_questions,
            total_marks: a.total_marks,
            passing_marks: a.passing_marks,
        });
        setShowAssessmentModal(true);
    };

    const handleEditSection = (s: Section) => {
        setSectionForm({
            id: s.id,
            title: s.title,
            instructions: s.instructions || '',
            order: s.order,
            passage: s.passage || '',
        });
        setShowSectionModal(true);
    };

    const handleEditQuestion = (q: Question) => {
        setQuestionForm({
            id: q.id,
            section_id: q.section_id,
            question_number: q.question_number || '',
            question_text: q.question_text,
            options: q.options || [{ id: 'i', text: '' }, { id: 'ii', text: '' }, { id: 'iii', text: '' }, { id: 'iv', text: '' }],
            correct_answer: q.correct_answer || '',
            marks: q.marks,
            difficulty: q.difficulty,
        });
        setShowQuestionModal(true);
    };

    const handleAddQuestion = (sectionId: number) => {
        resetQuestionForm();
        setQuestionForm(prev => ({ ...prev, section_id: sectionId }));
        setShowQuestionModal(true);
    };

    const handleViewAssessment = (a: Assessment) => {
        setSelectedAssessment(a);
        loadAssessment(a.id);
        setActiveTab('editor');
    };

    const formatDate = (dateStr: string) => new Date(dateStr).toLocaleDateString('en-GB');

    // ===== SUMMARY STATS =====
    const editorSummary = useMemo(() => {
        if (!selectedAssessment) return { sections: 0, questions: 0, marks: 0 };
        return {
            sections: selectedAssessment.sections.length,
            questions: selectedAssessment.total_questions,
            marks: selectedAssessment.total_marks,
        };
    }, [selectedAssessment]);

    return (
        <div className="assessment-management">
            {/* Header */}
            <div className="page-header">
                <h1><Brain size={28} /> Assessment Management</h1>
                <p className="page-subtitle">Create and manage standalone assessments with sections and auto-graded questions</p>
            </div>

            {/* Tab Menu */}
            <div className="tab-menu">
                <button className={`tab-btn ${activeTab === 'assessments' ? 'active' : ''}`} onClick={() => setActiveTab('assessments')}>
                    <ClipboardList size={18} /> Assessments
                </button>
                <button
                    className={`tab-btn ${activeTab === 'editor' ? 'active' : ''}`}
                    onClick={() => selectedAssessment && setActiveTab('editor')}
                    disabled={!selectedAssessment}
                >
                    <Wand2 size={18} /> Section Editor
                </button>
                <button
                    className={`tab-btn ${activeTab === 'results' ? 'active' : ''}`}
                    onClick={() => setActiveTab('results')}
                >
                    <BarChart2 size={18} /> Results
                </button>
            </div>

            {/* Error Display */}
            {error && <div className="error-banner">{error}</div>}

            {/* ===== ASSESSMENTS TAB ===== */}
            {activeTab === 'assessments' && (
                <div className="tab-content">
                    <div className="content-header">
                        <h2>All Assessments</h2>
                        <span className="count-badge">{assessments.length} assessments</span>
                        <button className="btn-primary" onClick={() => { resetAssessmentForm(); setShowAssessmentModal(true); }}>
                            <Plus size={16} /> New Assessment
                        </button>
                    </div>
                    {loading ? (
                        <div className="loading-state">Loading assessments...</div>
                    ) : (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>ASSESSMENT NAME</th>
                                    <th>CATEGORY</th>
                                    <th>DURATION</th>
                                    <th>QUESTIONS</th>
                                    <th>MARKS</th>
                                    <th>STATUS</th>
                                    <th>CREATED</th>
                                    <th>ACTIONS</th>
                                </tr>
                            </thead>
                            <tbody>
                                {assessments.length === 0 ? (
                                    <tr><td colSpan={8} className="empty-row">No assessments yet. Create one to get started.</td></tr>
                                ) : assessments.map(a => (
                                    <tr key={a.id}>
                                        <td className="assessment-name">{a.title}</td>
                                        <td><span className="category-badge">{a.category}</span></td>
                                        <td>{a.duration_minutes} min</td>
                                        <td>{a.total_questions}</td>
                                        <td>{a.total_marks}</td>
                                        <td>
                                            <span className={`status-badge ${a.is_published ? 'published' : 'draft'}`}>
                                                {a.is_published ? 'Published' : 'Draft'}
                                            </span>
                                        </td>
                                        <td>{formatDate(a.created_at)}</td>
                                        <td className="actions-cell">
                                            <button className="action-icon" onClick={() => handleViewAssessment(a)} title="Edit Sections">
                                                <Eye size={18} />
                                            </button>
                                            <button className="action-icon" onClick={() => handleEditAssessment(a)} title="Edit Details">
                                                <Edit2 size={18} />
                                            </button>
                                            {a.is_published ? (
                                                <button className="unpublish-btn" onClick={() => handleUnpublish(a.id)}>Unpublish</button>
                                            ) : (
                                                <button className="publish-btn" onClick={() => handlePublish(a.id)} disabled={a.total_questions === 0}>Publish</button>
                                            )}
                                            <button className="action-icon delete" onClick={() => setDeleteModal({ open: true, type: 'assessment', id: a.id, name: a.title })}>
                                                <Trash2 size={18} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}

            {/* ===== SECTION EDITOR TAB ===== */}
            {activeTab === 'editor' && selectedAssessment && (
                <div className="editor-layout">
                    <div className="editor-main">
                        <div className="editor-header">
                            <h2>{selectedAssessment.title}</h2>
                            <p>{selectedAssessment.description}</p>
                        </div>

                        <div className="sections-container">
                            <div className="sections-header">
                                <h3>Sections</h3>
                                <button className="btn-secondary" onClick={() => {
                                    resetSectionForm();
                                    setSectionForm(prev => ({ ...prev, order: selectedAssessment.sections.length + 1 }));
                                    setShowSectionModal(true);
                                }}>
                                    <Plus size={16} /> Add Section
                                </button>
                            </div>

                            {selectedAssessment.sections.length === 0 ? (
                                <div className="empty-sections">
                                    <Library size={48} />
                                    <p>No sections yet. Add a section to start adding questions.</p>
                                </div>
                            ) : (
                                selectedAssessment.sections
                                    .sort((a, b) => a.order - b.order)
                                    .map(section => (
                                        <SectionCard
                                            key={section.id}
                                            section={section}
                                            onAddQuestion={handleAddQuestion}
                                            onEditQuestion={handleEditQuestion}
                                            onDeleteQuestion={(id) => setDeleteModal({ open: true, type: 'question', id, name: 'this question' })}
                                            onEditSection={handleEditSection}
                                            onDeleteSection={(id) => setDeleteModal({ open: true, type: 'section', id, name: section.title })}
                                        />
                                    ))
                            )}
                        </div>
                    </div>

                    {/* Summary Panel */}
                    <div className="summary-panel">
                        <h3>Summary</h3>
                        <div className="summary-row">
                            <span>Category</span>
                            <span className="summary-value">{selectedAssessment.category}</span>
                        </div>
                        <div className="summary-row">
                            <span><Clock size={14} /> Duration</span>
                            <span className="summary-value">{selectedAssessment.duration_minutes} min</span>
                        </div>
                        <div className="summary-row">
                            <span>Sections</span>
                            <span className="summary-value">{editorSummary.sections}</span>
                        </div>
                        <div className="summary-row">
                            <span>Questions</span>
                            <span className="summary-value">{editorSummary.questions}</span>
                        </div>
                        <div className="summary-divider" />
                        <div className="summary-row total">
                            <span><Award size={14} /> Total Marks</span>
                            <span className="summary-value">{editorSummary.marks}</span>
                        </div>
                        <div className="summary-row">
                            <span>Passing Marks</span>
                            <span className="summary-value">{selectedAssessment.passing_marks}</span>
                        </div>

                        <div className="summary-status">
                            <span className={`status-badge ${selectedAssessment.is_published ? 'published' : 'draft'}`}>
                                {selectedAssessment.is_published ? 'Published' : 'Draft'}
                            </span>
                        </div>

                        {selectedAssessment.is_published ? (
                            <button className="btn-unpublish" onClick={() => handleUnpublish(selectedAssessment.id)}>
                                Unpublish
                            </button>
                        ) : (
                            <button
                                className="btn-publish"
                                onClick={() => handlePublish(selectedAssessment.id)}
                                disabled={selectedAssessment.total_questions === 0}
                            >
                                <FileText size={18} /> Publish Assessment
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* ===== RESULTS TAB ===== */}
            {activeTab === 'results' && (
                <div className="tab-content">
                    <div className="content-header">
                        <h2>Assessment Results</h2>
                        <span className="count-badge">{results.length} submissions</span>
                        <button className="btn-secondary" onClick={() => { setResults([]); loadResults(); }}>
                            Refresh
                        </button>
                    </div>
                    {results.length === 0 ? (
                        <div className="empty-state-results">
                            <BarChart2 size={48} />
                            <p>No assessment submissions yet</p>
                        </div>
                    ) : (
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>CANDIDATE</th>
                                    <th>ASSESSMENT</th>
                                    <th>SCORE</th>
                                    <th>TIME TAKEN</th>
                                    <th>STATUS</th>
                                    <th>COMPLETED</th>
                                </tr>
                            </thead>
                            <tbody>
                                {results.map(r => (
                                    <tr key={r.id}>
                                        <td>
                                            <div className="candidate-info">
                                                <User size={16} />
                                                <div>
                                                    <div className="candidate-name">{r.user_name}</div>
                                                    <div className="candidate-email">{r.user_email}</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td>
                                            <div className="assessment-info">
                                                <span className="assessment-name">{r.assessment_title}</span>
                                                {r.category && <span className="category-tag">{r.category}</span>}
                                            </div>
                                        </td>
                                        <td>
                                            <div className="score-info">
                                                <span className={`score ${r.passed ? 'passed' : 'failed'}`}>
                                                    {r.percentage?.toFixed(0)}%
                                                </span>
                                                <span className="marks">{r.score}/{r.total_marks}</span>
                                            </div>
                                        </td>
                                        <td>
                                            <span className="time-taken">
                                                {r.time_taken_seconds ? `${Math.floor(r.time_taken_seconds / 60)}m ${r.time_taken_seconds % 60}s` : 'N/A'}
                                            </span>
                                        </td>
                                        <td>
                                            <span className={`status-pill ${r.passed ? 'passed' : 'failed'}`}>
                                                {r.passed ? <CheckCircle size={14} /> : <XCircle size={14} />}
                                                {r.passed ? 'Passed' : 'Failed'}
                                            </span>
                                        </td>
                                        <td>
                                            {r.completed_at ? new Date(r.completed_at).toLocaleString('en-GB') : 'N/A'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            )}

            {/* ===== MODALS ===== */}

            {/* Assessment Modal */}
            {showAssessmentModal && (
                <div className="modal-overlay" onClick={() => setShowAssessmentModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>{assessmentForm.id ? 'Edit Assessment' : 'New Assessment'}</h2>
                            <button className="close-btn" onClick={() => setShowAssessmentModal(false)}><X size={20} /></button>
                        </div>
                        <div className="modal-body">
                            <div className="form-group">
                                <label>Title *</label>
                                <input
                                    placeholder="e.g. English Proficiency Test"
                                    value={assessmentForm.title}
                                    onChange={e => setAssessmentForm(p => ({ ...p, title: e.target.value }))}
                                />
                            </div>
                            <div className="form-group">
                                <label>Description</label>
                                <textarea
                                    rows={3}
                                    placeholder="Brief description of this assessment..."
                                    value={assessmentForm.description}
                                    onChange={e => setAssessmentForm(p => ({ ...p, description: e.target.value }))}
                                />
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>Category *</label>
                                    <select
                                        value={assessmentForm.category}
                                        onChange={e => setAssessmentForm(p => ({ ...p, category: e.target.value }))}
                                    >
                                        {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>Duration (mins)</label>
                                    <input
                                        type="number"
                                        min="1"
                                        value={assessmentForm.duration_minutes}
                                        onChange={e => setAssessmentForm(p => ({ ...p, duration_minutes: Number(e.target.value) }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Total Questions</label>
                                    <input
                                        type="number"
                                        min="0"
                                        value={assessmentForm.total_questions}
                                        onChange={e => setAssessmentForm(p => ({ ...p, total_questions: Number(e.target.value) }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Total Marks</label>
                                    <input
                                        type="number"
                                        min="0"
                                        value={assessmentForm.total_marks}
                                        onChange={e => setAssessmentForm(p => ({ ...p, total_marks: Number(e.target.value) }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Passing Marks</label>
                                    <input
                                        type="number"
                                        min="0"
                                        value={assessmentForm.passing_marks}
                                        onChange={e => setAssessmentForm(p => ({ ...p, passing_marks: Number(e.target.value) }))}
                                    />
                                </div>
                            </div>
                        </div>
                        <div className="modal-footer">
                            <button className="btn-secondary" onClick={() => setShowAssessmentModal(false)}>Cancel</button>
                            <button className="btn-primary" onClick={handleSaveAssessment} disabled={!assessmentForm.title.trim()}>
                                <Save size={16} /> {assessmentForm.id ? 'Update' : 'Create'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Section Modal */}
            {showSectionModal && (
                <div className="modal-overlay" onClick={() => setShowSectionModal(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>{sectionForm.id ? 'Edit Section' : 'New Section'}</h2>
                            <button className="close-btn" onClick={() => setShowSectionModal(false)}><X size={20} /></button>
                        </div>
                        <div className="modal-body">
                            <div className="form-group">
                                <label>Title *</label>
                                <input
                                    placeholder="e.g. Section A: Grammar & Vocabulary"
                                    value={sectionForm.title}
                                    onChange={e => setSectionForm(p => ({ ...p, title: e.target.value }))}
                                />
                            </div>
                            <div className="form-group">
                                <label>Instructions</label>
                                <textarea
                                    rows={2}
                                    placeholder="Instructions for this section..."
                                    value={sectionForm.instructions}
                                    onChange={e => setSectionForm(p => ({ ...p, instructions: e.target.value }))}
                                />
                            </div>
                            <div className="form-group">
                                <label>Passage (for Reading Comprehension)</label>
                                <textarea
                                    rows={4}
                                    placeholder="Enter reading passage if applicable..."
                                    value={sectionForm.passage}
                                    onChange={e => setSectionForm(p => ({ ...p, passage: e.target.value }))}
                                />
                            </div>
                            <div className="form-group">
                                <label>Order</label>
                                <input
                                    type="number"
                                    min="1"
                                    value={sectionForm.order}
                                    onChange={e => setSectionForm(p => ({ ...p, order: Number(e.target.value) }))}
                                />
                            </div>
                        </div>
                        <div className="modal-footer">
                            <button className="btn-secondary" onClick={() => setShowSectionModal(false)}>Cancel</button>
                            <button className="btn-primary" onClick={handleSaveSection} disabled={!sectionForm.title.trim()}>
                                <Save size={16} /> {sectionForm.id ? 'Update' : 'Create'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Question Modal */}
            {showQuestionModal && (
                <div className="modal-overlay" onClick={() => setShowQuestionModal(false)}>
                    <div className="modal wide" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>{questionForm.id ? 'Edit Question' : 'New Question'}</h2>
                            <button className="close-btn" onClick={() => setShowQuestionModal(false)}><X size={20} /></button>
                        </div>
                        <div className="modal-body">
                            <div className="form-row">
                                <div className="form-group small">
                                    <label>Q. Number</label>
                                    <input
                                        placeholder="e.g. 1a"
                                        value={questionForm.question_number}
                                        onChange={e => setQuestionForm(p => ({ ...p, question_number: e.target.value }))}
                                    />
                                </div>
                                <div className="form-group small">
                                    <label>Marks</label>
                                    <input
                                        type="number"
                                        min="0.5"
                                        step="0.5"
                                        value={questionForm.marks}
                                        onChange={e => setQuestionForm(p => ({ ...p, marks: Number(e.target.value) }))}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>Difficulty</label>
                                    <select
                                        value={questionForm.difficulty}
                                        onChange={e => setQuestionForm(p => ({ ...p, difficulty: e.target.value }))}
                                    >
                                        <option value="easy">Easy</option>
                                        <option value="medium">Medium</option>
                                        <option value="hard">Hard</option>
                                    </select>
                                </div>
                            </div>
                            <div className="form-group">
                                <label>Question Text *</label>
                                <textarea
                                    rows={3}
                                    placeholder="Enter the question..."
                                    value={questionForm.question_text}
                                    onChange={e => setQuestionForm(p => ({ ...p, question_text: e.target.value }))}
                                />
                            </div>
                            <div className="form-group">
                                <label>Options (MCQ)</label>
                                <div className="options-inputs">
                                    {questionForm.options.map((opt, i) => (
                                        <div key={opt.id} className="option-input-row">
                                            <span className="option-id">{opt.id})</span>
                                            <input
                                                placeholder={`Option ${opt.id}`}
                                                value={opt.text}
                                                onChange={e => {
                                                    const newOpts = [...questionForm.options];
                                                    newOpts[i] = { ...newOpts[i], text: e.target.value };
                                                    setQuestionForm(p => ({ ...p, options: newOpts }));
                                                }}
                                            />
                                            <button
                                                type="button"
                                                className={`correct-btn ${questionForm.correct_answer === opt.id ? 'selected' : ''}`}
                                                onClick={() => setQuestionForm(p => ({ ...p, correct_answer: opt.id }))}
                                                title="Mark as correct"
                                            >
                                                <CheckSquare size={18} />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                                <p className="form-hint">Click the checkmark to set the correct answer</p>
                            </div>
                        </div>
                        <div className="modal-footer">
                            <button className="btn-secondary" onClick={() => setShowQuestionModal(false)}>Cancel</button>
                            <button
                                className="btn-primary"
                                onClick={handleSaveQuestion}
                                disabled={!questionForm.question_text.trim() || !questionForm.correct_answer}
                            >
                                <Save size={16} /> {questionForm.id ? 'Update' : 'Add Question'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            {deleteModal.open && (
                <div className="modal-overlay" onClick={() => setDeleteModal({ open: false, type: '', id: null, name: '' })}>
                    <div className="modal small" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <h2>Confirm Delete</h2>
                            <button className="close-btn" onClick={() => setDeleteModal({ open: false, type: '', id: null, name: '' })}>
                                <X size={20} />
                            </button>
                        </div>
                        <div className="modal-body">
                            <p>Are you sure you want to delete <strong>{deleteModal.name}</strong>?</p>
                            {deleteModal.type === 'section' && <p className="warning-text">This will also delete all questions in this section.</p>}
                        </div>
                        <div className="modal-footer">
                            <button className="btn-secondary" onClick={() => setDeleteModal({ open: false, type: '', id: null, name: '' })}>Cancel</button>
                            <button className="btn-danger" onClick={confirmDelete}>Delete</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

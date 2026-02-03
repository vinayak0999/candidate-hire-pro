"""
Pydantic schemas for test-related API endpoints
"""
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


# ========== Division Schemas ==========

class DivisionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class DivisionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class DivisionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    documents: Optional[List[Dict[str, str]]] = None  # Shared Agent Analysis docs
    created_at: datetime
    test_count: Optional[int] = 0

    class Config:
        from_attributes = True


# ========== Question Schemas ==========

class QuestionCreate(BaseModel):
    question_type: str = "mcq"  # video, image, mcq, jumble, reading, agent_analysis
    question_text: str
    division_id: Optional[int] = None  # Division this question belongs to
    options: Optional[List[str]] = None  # For MCQ
    correct_answer: Optional[str] = None  # For MCQ
    media_url: Optional[str] = None  # For Video/Image
    passage: Optional[str] = None  # For Reading Comprehension
    sentences: Optional[List[str]] = None  # For Jumble-Tumble (correct order)
    html_content: Optional[str] = None  # For Agent Analysis: raw HTML, URL to .html, or URL to .pdf
    documents: Optional[List[Dict[str, str]]] = None  # For Agent Analysis [{id, title, content}] - content can be .html or .pdf URL
    annotation_data: Optional[Any] = None
    marks: float = 1.0
    difficulty: str = "medium"
    tags: Optional[List[str]] = None


class QuestionUpdate(BaseModel):
    question_type: Optional[str] = None
    question_text: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    media_url: Optional[str] = None
    marks: Optional[float] = None
    difficulty: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class QuestionResponse(BaseModel):
    id: int
    question_type: str
    question_text: str
    division_id: Optional[int] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    media_url: Optional[str] = None
    passage: Optional[str] = None
    sentences: Optional[List[str]] = None
    html_content: Optional[str] = None  # For Agent Analysis
    documents: Optional[List[Dict[str, Any]]] = None  # For Agent Analysis
    marks: float
    difficulty: str
    tags: Optional[List[str]] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# For test taking - without correct answer
class QuestionForTest(BaseModel):
    id: int
    question_type: str
    question_text: str
    options: Optional[List[str]] = None
    media_url: Optional[str] = None
    passage: Optional[str] = None  # For reading questions
    sentences: Optional[List[str]] = None  # For jumble questions (shuffled)
    html_content: Optional[str] = None  # For Agent Analysis: HTML content, .html URL, or .pdf URL
    documents: Optional[List[Dict[str, Any]]] = None  # For Agent Analysis: [{id, title, content}]
    marks: float

    class Config:
        from_attributes = True


# ========== Test Schemas ==========

class TestModuleConfig(BaseModel):
    """Configuration for a question module in test generation"""
    enabled: bool = True
    count: int = 10
    marks_per_question: float = 1.0


class SectionConfig(BaseModel):
    """Section configuration with difficulty breakdown"""
    enabled: bool = True
    marks_per_question: float = 10.0
    hard: int = 0
    medium: int = 0
    easy: int = 0


class TestGenerateRequest(BaseModel):
    """Request to generate a new test"""
    title: str
    description: Optional[str] = None
    division_id: Optional[int] = None
    duration_minutes: int = 60
    
    # New format: sections with difficulty breakdown
    sections: Optional[Dict[str, SectionConfig]] = None
    
    # Legacy module configurations (backwards compatibility)
    mcq: Optional[TestModuleConfig] = None
    text_annotation: Optional[TestModuleConfig] = None
    image_annotation: Optional[TestModuleConfig] = None
    video_annotation: Optional[TestModuleConfig] = None
    
    # Anti-cheat config
    enable_tab_switch_detection: bool = True
    max_tab_switches_allowed: int = 3


class TestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    division_id: Optional[int] = None
    duration_minutes: int = 60
    passing_marks: float = 0
    enable_tab_switch_detection: bool = True
    max_tab_switches_allowed: int = 3


class TestUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    division_id: Optional[int] = None
    duration_minutes: Optional[int] = None
    passing_marks: Optional[float] = None
    is_active: Optional[bool] = None
    is_published: Optional[bool] = None
    enable_tab_switch_detection: Optional[bool] = None
    max_tab_switches_allowed: Optional[int] = None


class TestResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    division_id: Optional[int] = None
    division_name: Optional[str] = None
    duration_minutes: int
    total_questions: int
    total_marks: float
    passing_marks: float
    mcq_count: int
    text_annotation_count: int
    image_annotation_count: int
    video_annotation_count: int
    agent_analysis_count: int = 0
    is_active: bool
    is_published: bool
    created_at: datetime
    enable_tab_switch_detection: bool = True
    max_tab_switches_allowed: int = 3

    class Config:
        from_attributes = True


# ========== Test Attempt Schemas ==========

class StartTestRequest(BaseModel):
    test_id: int


class SubmitAnswerRequest(BaseModel):
    question_id: int
    answer_text: Optional[str] = None
    annotation_data: Optional[Any] = None
    time_spent_seconds: Optional[int] = None


class CompleteTestRequest(BaseModel):
    attempt_id: int
    tab_switches: Optional[int] = 0


class TestAttemptResponse(BaseModel):
    id: int
    test_id: int
    test_title: Optional[str] = None
    status: str
    current_question: int
    score: float
    total_marks: float
    percentage: float
    passed: bool
    tab_switches: int
    is_flagged: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    time_taken_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class TestSessionResponse(BaseModel):
    """Response when starting a test session"""
    attempt_id: int
    test_id: int
    test_title: str
    duration_minutes: int
    total_questions: int
    questions: List[QuestionForTest]
    started_at: datetime
    enable_tab_switch_detection: bool = True
    max_tab_switches_allowed: int = 3


class TestResultResponse(BaseModel):
    """Detailed test result after completion"""
    attempt_id: int
    test_id: int
    test_title: str
    score: float
    total_marks: float
    percentage: float
    passed: bool
    time_taken_seconds: int
    completed_at: datetime
    answers: List[dict]  # Question with user answer and correctness


# ========== Admin Stats Schemas ==========

class AdminDashboardStats(BaseModel):
    total_candidates: int
    active_jobs: int
    tests_completed: int
    flagged_attempts: int
    
    # Performance metrics
    mcq_pass_rate: float
    text_annotation_pass_rate: float
    image_annotation_pass_rate: float
    video_annotation_pass_rate: float


class CandidateListItem(BaseModel):
    id: int
    name: str
    email: str
    applied_job: Optional[str] = None
    progress: float  # 0-100
    status: str  # applied, in_progress, completed, flagged
    last_activity: Optional[datetime] = None


class ReportData(BaseModel):
    report_type: str
    data: Any
    generated_at: datetime


# ========== Standalone Assessment Schemas (Section-based) ==========

class OptionSchema(BaseModel):
    """MCQ option with id and text"""
    id: str  # e.g., "i", "ii", "iii", "iv"
    text: str


class SectionQuestionCreate(BaseModel):
    """Question within a section"""
    question_number: Optional[str] = None  # e.g., "1a", "2b"
    question_type: str = "mcq"
    question_text: str
    options: Optional[List[OptionSchema]] = None
    correct_answer: Optional[str] = None  # Option id for MCQ (e.g., "ii")
    passage_id: Optional[str] = None  # Groups questions under same passage
    marks: float = 1.0
    difficulty: str = "medium"


class SectionQuestionUpdate(BaseModel):
    """Update question within a section"""
    question_number: Optional[str] = None
    question_type: Optional[str] = None
    question_text: Optional[str] = None
    options: Optional[List[OptionSchema]] = None
    correct_answer: Optional[str] = None
    passage_id: Optional[str] = None
    marks: Optional[float] = None
    difficulty: Optional[str] = None
    is_active: Optional[bool] = None


class SectionQuestionResponse(BaseModel):
    """Question response including correct answer (admin only)"""
    id: int
    section_id: Optional[int] = None
    question_number: Optional[str] = None
    question_type: str
    question_text: str
    options: Optional[List[Dict[str, str]]] = None  # [{id, text}]
    correct_answer: Optional[str] = None
    passage_id: Optional[str] = None
    marks: float
    difficulty: Optional[str] = "medium"
    is_active: Optional[bool] = True
    created_at: datetime

    class Config:
        from_attributes = True


class SectionQuestionForCandidate(BaseModel):
    """Question for candidate (no correct answer)"""
    id: int
    question_number: Optional[str] = None
    question_type: str
    question_text: str
    options: Optional[List[Dict[str, str]]] = None
    passage_id: Optional[str] = None
    marks: float

    class Config:
        from_attributes = True


class SectionCreate(BaseModel):
    """Create a section within an assessment"""
    title: str  # e.g., "Section A: Grammar & Vocabulary"
    instructions: Optional[str] = None
    total_marks: float = 0
    order: int = 0
    passage: Optional[str] = None  # For reading comprehension sections


class SectionUpdate(BaseModel):
    """Update a section"""
    title: Optional[str] = None
    instructions: Optional[str] = None
    total_marks: Optional[float] = None
    order: Optional[int] = None
    passage: Optional[str] = None


class SectionResponse(BaseModel):
    """Section response with questions"""
    id: int
    test_id: int
    title: str
    instructions: Optional[str] = None
    total_marks: Optional[float] = 0.0
    order: Optional[int] = 0
    passage: Optional[str] = None
    questions: List[SectionQuestionResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class SectionForCandidate(BaseModel):
    """Section for candidate (no correct answers in questions)"""
    id: int
    title: str
    instructions: Optional[str] = None
    total_marks: Optional[float] = 0.0
    order: Optional[int] = 0
    passage: Optional[str] = None
    questions: List[SectionQuestionForCandidate] = []

    class Config:
        from_attributes = True


class StandaloneAssessmentCreate(BaseModel):
    """Create a standalone assessment"""
    title: str
    description: Optional[str] = None
    category: str  # "English", "Logical", "Technical", etc.
    duration_minutes: int = 60
    passing_marks: float = 0
    enable_tab_switch_detection: bool = True
    max_tab_switches_allowed: int = 3


class StandaloneAssessmentUpdate(BaseModel):
    """Update a standalone assessment"""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    duration_minutes: Optional[int] = None
    total_questions: Optional[int] = None  # Can override calculated value
    total_marks: Optional[float] = None    # Can override calculated value
    passing_marks: Optional[float] = None
    is_active: Optional[bool] = None
    is_published: Optional[bool] = None
    enable_tab_switch_detection: Optional[bool] = None
    max_tab_switches_allowed: Optional[int] = None


class StandaloneAssessmentResponse(BaseModel):
    """Standalone assessment response"""
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    assessment_type: str = "standalone_assessment"
    duration_minutes: int
    total_questions: int
    total_marks: float
    passing_marks: float
    is_active: bool
    is_published: bool
    enable_tab_switch_detection: bool
    max_tab_switches_allowed: int
    created_at: datetime
    sections: List[SectionResponse] = []

    class Config:
        from_attributes = True


class StandaloneAssessmentForCandidate(BaseModel):
    """Assessment for candidate view (no correct answers)"""
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    duration_minutes: int
    total_questions: int
    total_marks: float
    passing_marks: float

    class Config:
        from_attributes = True


# ========== Candidate Assessment Taking Schemas ==========

class StartAssessmentRequest(BaseModel):
    """Request to start an assessment"""
    assessment_id: int


class AssessmentSessionResponse(BaseModel):
    """Response when starting an assessment session"""
    attempt_id: int
    assessment_id: int
    assessment_title: str
    duration_minutes: int
    total_questions: int
    total_marks: float
    sections: List[SectionForCandidate]
    started_at: datetime
    enable_tab_switch_detection: bool
    max_tab_switches_allowed: int


class SubmitAssessmentAnswerRequest(BaseModel):
    """Submit answer for a question"""
    question_id: int
    selected_option: str  # Option id (e.g., "ii")
    time_spent_seconds: Optional[int] = None


class SubmitAssessmentRequest(BaseModel):
    """Submit entire assessment"""
    attempt_id: int
    answers: List[SubmitAssessmentAnswerRequest]
    tab_switches: int = 0


class AnswerResult(BaseModel):
    """Result for a single answer"""
    question_id: int
    question_number: Optional[str] = None
    question_text: str
    user_answer: Optional[str] = None
    correct_answer: str
    is_correct: bool
    marks_obtained: float
    max_marks: float


class SectionResult(BaseModel):
    """Result for a section"""
    section_id: int
    section_title: str
    total_marks: float
    marks_obtained: float
    questions: List[AnswerResult]


class AssessmentResultResponse(BaseModel):
    """Detailed assessment result after completion"""
    attempt_id: int
    assessment_id: int
    assessment_title: str
    category: Optional[str] = None
    score: float
    total_marks: float
    percentage: float
    passed: bool
    time_taken_seconds: int
    completed_at: datetime
    sections: List[SectionResult]


class AvailableAssessmentResponse(BaseModel):
    """Assessment available for candidate"""
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    duration_minutes: int
    total_questions: int
    total_marks: float
    passing_marks: float
    status: str = "not_started"  # not_started, in_progress, completed
    best_score: Optional[float] = None
    best_percentage: Optional[float] = None
    last_attempt_at: Optional[datetime] = None

    class Config:
        from_attributes = True


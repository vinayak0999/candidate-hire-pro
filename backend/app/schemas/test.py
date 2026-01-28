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
    html_content: Optional[str] = None  # For Agent Analysis (iframe content)
    documents: Optional[List[Dict[str, str]]] = None  # For Agent Analysis [{id, title, content}]
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
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    media_url: Optional[str] = None
    passage: Optional[str] = None
    sentences: Optional[List[str]] = None
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
    html_content: Optional[str] = None  # For Agent Analysis
    documents: Optional[List[Dict[str, Any]]] = None  # For Agent Analysis
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

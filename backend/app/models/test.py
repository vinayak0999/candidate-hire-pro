"""
Division, Question, Test models for the assessment system
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base
import enum


class QuestionType(str, enum.Enum):
    MCQ = "mcq"
    TEXT_ANNOTATION = "text_annotation"
    IMAGE_ANNOTATION = "image_annotation"
    VIDEO_ANNOTATION = "video_annotation"


class Division(Base):
    """Divisions group tests by category (e.g., Data Annotator, QA Analyst)"""
    __tablename__ = "divisions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tests = relationship("Test", back_populates="division")


class Question(Base):
    """Individual questions that can be added to tests"""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True)  # Division this question belongs to
    question_type = Column(String(50), nullable=False, default=QuestionType.MCQ)
    question_text = Column(Text, nullable=False)
    
    # For MCQ questions
    options = Column(JSON, nullable=True)  # List of options
    correct_answer = Column(String(500), nullable=True)  # For MCQ: option index or text
    
    # For annotation questions (video/image)
    media_url = Column(String(500), nullable=True)  # Image/video URL
    annotation_data = Column(JSON, nullable=True)  # Expected annotation data
    
    # For Reading Comprehension
    passage = Column(Text, nullable=True)  # Reading passage text
    
    # For Jumble-Tumble (sentences in correct order)
    sentences = Column(JSON, nullable=True)  # List of sentences in correct order
    
    marks = Column(Float, default=1.0)
    difficulty = Column(String(20), default="medium")  # easy, medium, hard
    tags = Column(JSON, nullable=True)  # For categorization
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    test_questions = relationship("TestQuestion", back_populates="question")


class Test(Base):
    """Generated tests that consist of multiple questions"""
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True)
    
    # Test configuration
    duration_minutes = Column(Integer, default=60)
    total_questions = Column(Integer, default=0)
    total_marks = Column(Float, default=0)
    passing_marks = Column(Float, default=0)
    
    # Module counts (for test generation)
    mcq_count = Column(Integer, default=0)
    text_annotation_count = Column(Integer, default=0)
    image_annotation_count = Column(Integer, default=0)
    video_annotation_count = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    division = relationship("Division", back_populates="tests")
    test_questions = relationship("TestQuestion", back_populates="test")
    attempts = relationship("TestAttempt", back_populates="test")


class TestQuestion(Base):
    """Junction table linking tests to questions with ordering"""
    __tablename__ = "test_questions"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    order = Column(Integer, default=0)  # Question order in test
    
    # Relationships
    test = relationship("Test", back_populates="test_questions")
    question = relationship("Question", back_populates="test_questions")


class TestAttempt(Base):
    """User's attempt at taking a test"""
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id"), nullable=False)
    
    # Progress tracking
    status = Column(String(20), default="in_progress")  # in_progress, completed, abandoned
    current_question = Column(Integer, default=0)
    
    # Scoring
    score = Column(Float, default=0)
    total_marks = Column(Float, default=0)
    percentage = Column(Float, default=0)
    passed = Column(Boolean, default=False)
    
    # Anti-cheating flags
    tab_switches = Column(Integer, default=0)
    fullscreen_exits = Column(Integer, default=0)
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String(500), nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)
    
    # Relationships
    test = relationship("Test", back_populates="attempts")
    answers = relationship("UserAnswer", back_populates="attempt")


class UserAnswer(Base):
    """Individual user answers for a test attempt"""
    __tablename__ = "user_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("test_attempts.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    
    # Answer data
    answer_text = Column(Text, nullable=True)  # For MCQ or text answers
    annotation_data = Column(JSON, nullable=True)  # For annotation answers
    
    # Scoring
    is_correct = Column(Boolean, nullable=True)
    marks_obtained = Column(Float, default=0)
    
    answered_at = Column(DateTime(timezone=True), server_default=func.now())
    time_spent_seconds = Column(Integer, nullable=True)
    
    # Relationships
    attempt = relationship("TestAttempt", back_populates="answers")

"""
Standalone Assessment Management Router
Provides CRUD for section-based assessments with auto-evaluation
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, delete
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from ..database import get_db
from ..models.user import User, UserRole
from ..models.test import Test, TestSection, Question, TestAttempt, UserAnswer
from ..schemas.test import (
    # Section schemas
    SectionCreate, SectionUpdate, SectionResponse,
    SectionQuestionCreate, SectionQuestionUpdate, SectionQuestionResponse,
    SectionForCandidate, SectionQuestionForCandidate,
    # Assessment schemas
    StandaloneAssessmentCreate, StandaloneAssessmentUpdate, 
    StandaloneAssessmentResponse, StandaloneAssessmentForCandidate,
    AvailableAssessmentResponse,
    # Candidate taking schemas
    StartAssessmentRequest, AssessmentSessionResponse,
    SubmitAssessmentRequest, SubmitAssessmentAnswerRequest,
    AssessmentResultResponse, SectionResult, AnswerResult,
)
from ..services.auth import get_current_user

router = APIRouter(prefix="/api/standalone-assessments", tags=["Standalone Assessments"])


# ========== Helper Functions ==========

def require_admin(user: User):
    """Verify user has admin role"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


async def get_assessment_or_404(db: AsyncSession, assessment_id: int) -> Test:
    """Get standalone assessment by ID or raise 404"""
    result = await db.execute(
        select(Test)
        .options(
            selectinload(Test.sections).selectinload(TestSection.questions)
        )
        .where(
            and_(
                Test.id == assessment_id,
                Test.assessment_type == "standalone_assessment"
            )
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    return assessment


async def get_section_or_404(db: AsyncSession, section_id: int) -> TestSection:
    """Get section by ID or raise 404"""
    result = await db.execute(
        select(TestSection)
        .options(selectinload(TestSection.questions))
        .where(TestSection.id == section_id)
    )
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found"
        )
    return section


async def recalculate_assessment_totals(db: AsyncSession, assessment_id: int):
    """Recalculate total_questions and total_marks for an assessment"""
    # Get all sections with questions
    result = await db.execute(
        select(TestSection)
        .options(selectinload(TestSection.questions))
        .where(TestSection.test_id == assessment_id)
    )
    sections = result.scalars().all()
    
    total_questions = 0
    total_marks = 0.0
    
    for section in sections:
        active_questions = [q for q in section.questions if q.is_active]
        total_questions += len(active_questions)
        total_marks += sum(q.marks for q in active_questions)
        # Update section total_marks
        section.total_marks = sum(q.marks for q in active_questions)
    
    # Update assessment
    assessment = await db.get(Test, assessment_id)
    if assessment:
        assessment.total_questions = total_questions
        assessment.total_marks = total_marks
    
    await db.commit()


def format_section_response(section: TestSection) -> dict:
    """Format section with questions for response"""
    return {
        "id": section.id,
        "test_id": section.test_id,
        "title": section.title,
        "instructions": section.instructions,
        "total_marks": section.total_marks,
        "order": section.order,
        "passage": section.passage,
        "created_at": section.created_at,
        "questions": [
            {
                "id": q.id,
                "section_id": q.section_id,
                "question_number": q.question_number,
                "question_type": q.question_type,
                "question_text": q.question_text,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "passage_id": q.passage_id,
                "marks": q.marks,
                "difficulty": q.difficulty,
                "is_active": q.is_active,
                "created_at": q.created_at,
            }
            for q in section.questions if q.is_active
        ]
    }


def format_assessment_response(assessment: Test) -> dict:
    """Format assessment with sections for response"""
    return {
        "id": assessment.id,
        "title": assessment.title,
        "description": assessment.description,
        "category": assessment.category,
        "assessment_type": assessment.assessment_type,
        "duration_minutes": assessment.duration_minutes,
        "total_questions": assessment.total_questions,
        "total_marks": assessment.total_marks,
        "passing_marks": assessment.passing_marks,
        "is_active": assessment.is_active,
        "is_published": assessment.is_published,
        "enable_tab_switch_detection": assessment.enable_tab_switch_detection,
        "max_tab_switches_allowed": assessment.max_tab_switches_allowed,
        "created_at": assessment.created_at,
        "sections": [format_section_response(s) for s in sorted(assessment.sections, key=lambda x: x.order)]
    }


# ========== Assessment CRUD (Admin) ==========

@router.get("", response_model=List[StandaloneAssessmentResponse])
async def list_assessments(
    category: Optional[str] = None,
    published_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all standalone assessments (admin only)"""
    require_admin(current_user)
    
    query = select(Test).options(
        selectinload(Test.sections).selectinload(TestSection.questions)
    ).where(Test.assessment_type == "standalone_assessment")
    
    if category:
        query = query.where(Test.category == category)
    if published_only:
        query = query.where(Test.is_published == True)
    
    query = query.order_by(Test.created_at.desc())
    
    result = await db.execute(query)
    assessments = result.scalars().all()
    
    return [format_assessment_response(a) for a in assessments]


@router.post("", response_model=StandaloneAssessmentResponse)
async def create_assessment(
    data: StandaloneAssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new standalone assessment"""
    require_admin(current_user)
    
    assessment = Test(
        title=data.title,
        description=data.description,
        category=data.category,
        assessment_type="standalone_assessment",
        duration_minutes=data.duration_minutes,
        passing_marks=data.passing_marks,
        enable_tab_switch_detection=data.enable_tab_switch_detection,
        max_tab_switches_allowed=data.max_tab_switches_allowed,
        total_questions=0,
        total_marks=0,
        is_published=False,
        is_active=True
    )
    
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    
    # Reload with sections
    assessment = await get_assessment_or_404(db, assessment.id)
    return format_assessment_response(assessment)


@router.get("/{assessment_id}", response_model=StandaloneAssessmentResponse)
async def get_assessment(
    assessment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single assessment with all sections and questions"""
    require_admin(current_user)
    
    assessment = await get_assessment_or_404(db, assessment_id)
    return format_assessment_response(assessment)


@router.put("/{assessment_id}", response_model=StandaloneAssessmentResponse)
async def update_assessment(
    assessment_id: int,
    data: StandaloneAssessmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an assessment"""
    require_admin(current_user)
    
    assessment = await get_assessment_or_404(db, assessment_id)
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(assessment, key, value)
    
    await db.commit()
    await db.refresh(assessment)
    
    # Reload with sections
    assessment = await get_assessment_or_404(db, assessment_id)
    return format_assessment_response(assessment)


@router.delete("/{assessment_id}")
async def delete_assessment(
    assessment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft delete an assessment"""
    require_admin(current_user)
    
    assessment = await get_assessment_or_404(db, assessment_id)
    assessment.is_active = False
    await db.commit()
    
    return {"message": "Assessment deleted successfully"}


@router.post("/{assessment_id}/publish")
async def publish_assessment(
    assessment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Publish an assessment"""
    require_admin(current_user)
    
    assessment = await get_assessment_or_404(db, assessment_id)
    
    # Validate assessment has at least one question
    if assessment.total_questions == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish assessment with no questions"
        )
    
    assessment.is_published = True
    assessment.is_active = True  # Ensure assessment is active when published
    await db.commit()
    
    return {"message": "Assessment published successfully"}


@router.post("/{assessment_id}/unpublish")
async def unpublish_assessment(
    assessment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unpublish an assessment"""
    require_admin(current_user)
    
    assessment = await get_assessment_or_404(db, assessment_id)
    assessment.is_published = False
    await db.commit()
    
    return {"message": "Assessment unpublished successfully"}


# ========== Section CRUD ==========

@router.post("/{assessment_id}/sections", response_model=SectionResponse)
async def create_section(
    assessment_id: int,
    data: SectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a section to an assessment"""
    require_admin(current_user)
    
    # Verify assessment exists
    assessment = await get_assessment_or_404(db, assessment_id)
    
    # Auto-calculate order if not provided
    if data.order == 0:
        data.order = len(assessment.sections) + 1
    
    section = TestSection(
        test_id=assessment_id,
        title=data.title,
        instructions=data.instructions,
        total_marks=data.total_marks,
        order=data.order,
        passage=data.passage
    )
    
    db.add(section)
    await db.commit()
    await db.refresh(section)
    
    # Reload with questions
    section = await get_section_or_404(db, section.id)
    return format_section_response(section)


@router.put("/sections/{section_id}", response_model=SectionResponse)
async def update_section(
    section_id: int,
    data: SectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a section"""
    require_admin(current_user)
    
    section = await get_section_or_404(db, section_id)
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(section, key, value)
    
    await db.commit()
    await db.refresh(section)
    
    # Reload with questions
    section = await get_section_or_404(db, section_id)
    return format_section_response(section)


@router.delete("/sections/{section_id}")
async def delete_section(
    section_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a section and its questions"""
    require_admin(current_user)
    
    section = await get_section_or_404(db, section_id)
    assessment_id = section.test_id
    
    # Get all question IDs in this section
    question_ids = [q.id for q in section.questions]
    
    # First delete user_answers that reference these questions (to avoid FK violation)
    if question_ids:
        await db.execute(
            delete(UserAnswer).where(UserAnswer.question_id.in_(question_ids))
        )
    
    # Delete questions in section
    for question in section.questions:
        await db.delete(question)
    
    await db.delete(section)
    await db.commit()
    
    # Recalculate totals
    await recalculate_assessment_totals(db, assessment_id)
    
    return {"message": "Section deleted successfully"}


# ========== Question CRUD ==========

@router.post("/sections/{section_id}/questions", response_model=SectionQuestionResponse)
async def create_question(
    section_id: int,
    data: SectionQuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a question to a section"""
    require_admin(current_user)
    
    section = await get_section_or_404(db, section_id)
    
    # Convert options to dict format if provided
    options = None
    if data.options:
        options = [{"id": o.id, "text": o.text} for o in data.options]
    
    question = Question(
        section_id=section_id,
        question_number=data.question_number,
        question_type=data.question_type,
        question_text=data.question_text,
        options=options,
        correct_answer=data.correct_answer,
        passage_id=data.passage_id,
        marks=data.marks,
        difficulty=data.difficulty,
        is_active=True
    )
    
    db.add(question)
    await db.commit()
    await db.refresh(question)
    
    # Recalculate totals
    await recalculate_assessment_totals(db, section.test_id)
    
    return {
        "id": question.id,
        "section_id": question.section_id,
        "question_number": question.question_number,
        "question_type": question.question_type,
        "question_text": question.question_text,
        "options": question.options,
        "correct_answer": question.correct_answer,
        "passage_id": question.passage_id,
        "marks": question.marks,
        "difficulty": question.difficulty,
        "is_active": question.is_active,
        "created_at": question.created_at,
    }


@router.post("/sections/{section_id}/questions/bulk", response_model=List[SectionQuestionResponse])
async def create_questions_bulk(
    section_id: int,
    questions: List[SectionQuestionCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add multiple questions to a section"""
    require_admin(current_user)
    
    section = await get_section_or_404(db, section_id)
    created_questions = []
    
    for data in questions:
        options = None
        if data.options:
            options = [{"id": o.id, "text": o.text} for o in data.options]
        
        question = Question(
            section_id=section_id,
            question_number=data.question_number,
            question_type=data.question_type,
            question_text=data.question_text,
            options=options,
            correct_answer=data.correct_answer,
            passage_id=data.passage_id,
            marks=data.marks,
            difficulty=data.difficulty,
            is_active=True
        )
        
        db.add(question)
        created_questions.append(question)
    
    await db.commit()
    
    # Refresh all questions
    for q in created_questions:
        await db.refresh(q)
    
    # Recalculate totals
    await recalculate_assessment_totals(db, section.test_id)
    
    return [
        {
            "id": q.id,
            "section_id": q.section_id,
            "question_number": q.question_number,
            "question_type": q.question_type,
            "question_text": q.question_text,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "passage_id": q.passage_id,
            "marks": q.marks,
            "difficulty": q.difficulty,
            "is_active": q.is_active,
            "created_at": q.created_at,
        }
        for q in created_questions
    ]


@router.put("/questions/{question_id}", response_model=SectionQuestionResponse)
async def update_question(
    question_id: int,
    data: SectionQuestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a question"""
    require_admin(current_user)
    
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Convert options if provided
    if "options" in update_data and update_data["options"]:
        update_data["options"] = [{"id": o.id, "text": o.text} for o in data.options]
    
    for key, value in update_data.items():
        setattr(question, key, value)
    
    await db.commit()
    await db.refresh(question)
    
    # Recalculate totals if marks changed
    if question.section_id:
        section = await get_section_or_404(db, question.section_id)
        await recalculate_assessment_totals(db, section.test_id)
    
    return {
        "id": question.id,
        "section_id": question.section_id,
        "question_number": question.question_number,
        "question_type": question.question_type,
        "question_text": question.question_text,
        "options": question.options,
        "correct_answer": question.correct_answer,
        "passage_id": question.passage_id,
        "marks": question.marks,
        "difficulty": question.difficulty,
        "is_active": question.is_active,
        "created_at": question.created_at,
    }


@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a question"""
    require_admin(current_user)
    
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    section_id = question.section_id
    await db.delete(question)
    await db.commit()
    
    # Recalculate totals
    if section_id:
        section = await get_section_or_404(db, section_id)
        await recalculate_assessment_totals(db, section.test_id)
    
    return {"message": "Question deleted successfully"}


# ========== Candidate Endpoints ==========

@router.get("/candidate/available", response_model=List[AvailableAssessmentResponse])
async def get_available_assessments(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all available assessments for candidate"""
    query = select(Test).where(
        and_(
            Test.assessment_type == "standalone_assessment",
            Test.is_published == True,
            Test.is_active == True
        )
    )
    
    if category:
        query = query.where(Test.category == category)
    
    query = query.order_by(Test.category, Test.title)
    
    result = await db.execute(query)
    assessments = result.scalars().all()
    
    # Get user's attempts for status
    attempts_result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.user_id == current_user.id)
    )
    attempts = attempts_result.scalars().all()
    
    # Map attempts by test_id
    attempts_by_test = {}
    for attempt in attempts:
        if attempt.test_id not in attempts_by_test:
            attempts_by_test[attempt.test_id] = []
        attempts_by_test[attempt.test_id].append(attempt)
    
    response = []
    for assessment in assessments:
        user_attempts = attempts_by_test.get(assessment.id, [])
        
        # Determine status
        status = "not_started"
        best_score = None
        best_percentage = None
        last_attempt_at = None
        
        if user_attempts:
            completed_attempts = [a for a in user_attempts if a.status == "completed"]
            in_progress = [a for a in user_attempts if a.status == "in_progress"]
            
            if completed_attempts:
                status = "completed"
                best = max(completed_attempts, key=lambda a: a.percentage)
                best_score = best.score
                best_percentage = best.percentage
                last_attempt_at = max(a.completed_at or a.started_at for a in completed_attempts)
            elif in_progress:
                status = "in_progress"
                last_attempt_at = max(a.started_at for a in in_progress)
        
        response.append({
            "id": assessment.id,
            "title": assessment.title,
            "description": assessment.description,
            "category": assessment.category,
            "duration_minutes": assessment.duration_minutes,
            "total_questions": assessment.total_questions,
            "total_marks": assessment.total_marks,
            "passing_marks": assessment.passing_marks,
            "status": status,
            "best_score": best_score,
            "best_percentage": best_percentage,
            "last_attempt_at": last_attempt_at,
        })
    
    return response


@router.post("/candidate/start", response_model=AssessmentSessionResponse)
async def start_assessment(
    data: StartAssessmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start an assessment attempt"""
    # Get assessment with sections and questions
    result = await db.execute(
        select(Test)
        .options(
            selectinload(Test.sections).selectinload(TestSection.questions)
        )
        .where(
            and_(
                Test.id == data.assessment_id,
                Test.assessment_type == "standalone_assessment",
                Test.is_published == True,
                Test.is_active == True
            )
        )
    )
    assessment = result.scalar_one_or_none()
    
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found or not available"
        )
    
    # CRITICAL: Check if user already completed this assessment (single attempt only)
    completed_check = await db.execute(
        select(TestAttempt).where(
            and_(
                TestAttempt.user_id == current_user.id,
                TestAttempt.test_id == data.assessment_id,
                TestAttempt.status == "completed"
            )
        )
    )
    completed_attempt = completed_check.scalars().first()
    
    if completed_attempt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already completed this assessment. Only one attempt is allowed."
        )
    
    # Check for existing in-progress attempt
    existing_result = await db.execute(
        select(TestAttempt).where(
            and_(
                TestAttempt.user_id == current_user.id,
                TestAttempt.test_id == data.assessment_id,
                TestAttempt.status == "in_progress"
            )
        ).order_by(TestAttempt.started_at.desc())
    )
    existing_attempt = existing_result.scalars().first()
    
    if existing_attempt:
        # Return existing attempt
        attempt = existing_attempt
    else:
        # Create new attempt
        attempt = TestAttempt(
            user_id=current_user.id,
            test_id=data.assessment_id,
            status="in_progress",
            current_question=0,
            score=0,
            total_marks=assessment.total_marks,
            tab_switches=0
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
    
    # Format sections for candidate (no correct answers)
    sections_for_candidate = []
    for section in sorted(assessment.sections, key=lambda s: s.order):
        questions = []
        for q in section.questions:
            if q.is_active:
                questions.append({
                    "id": q.id,
                    "question_number": q.question_number,
                    "question_type": q.question_type,
                    "question_text": q.question_text,
                    "options": q.options,
                    "passage_id": q.passage_id,
                    "marks": q.marks,
                })
        
        sections_for_candidate.append({
            "id": section.id,
            "title": section.title,
            "instructions": section.instructions,
            "total_marks": section.total_marks,
            "order": section.order,
            "passage": section.passage,
            "questions": questions,
        })
    
    return {
        "attempt_id": attempt.id,
        "assessment_id": assessment.id,
        "assessment_title": assessment.title,
        "duration_minutes": assessment.duration_minutes,
        "total_questions": assessment.total_questions,
        "total_marks": assessment.total_marks,
        "sections": sections_for_candidate,
        "started_at": attempt.started_at,
        "enable_tab_switch_detection": assessment.enable_tab_switch_detection,
        "max_tab_switches_allowed": assessment.max_tab_switches_allowed,
    }


# ========== Auto-Save Endpoint (for continuous saving) ==========

class AnswerSubmission(BaseModel):
    question_id: int
    selected_option: str
    time_spent_seconds: int = 0


class AutoSaveRequest(BaseModel):
    attempt_id: int
    answers: List[AnswerSubmission]
    tab_switches: int = 0


@router.post("/candidate/auto-save")
async def auto_save_assessment(
    data: AutoSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Auto-save answers periodically during assessment.
    Called every 30 seconds by frontend.
    CRITICAL: This ensures no data loss even if browser crashes.
    """
    # Get attempt
    result = await db.execute(
        select(TestAttempt).where(
            and_(
                TestAttempt.id == data.attempt_id,
                TestAttempt.user_id == current_user.id,
                TestAttempt.status == "in_progress"
            )
        )
    )
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        return {"success": False, "message": "Attempt not found or already completed"}
    
    # Get all questions for this assessment
    assessment_result = await db.execute(
        select(Test)
        .options(selectinload(Test.sections).selectinload(TestSection.questions))
        .where(Test.id == attempt.test_id)
    )
    assessment = assessment_result.scalar_one_or_none()
    
    if not assessment:
        return {"success": False, "message": "Assessment not found"}
    
    # Build question lookup
    question_lookup = {}
    for section in assessment.sections:
        for q in section.questions:
            question_lookup[q.id] = q
    
    # Helper to normalize answer to option ID
    def normalize_answer(options, text_or_id):
        """Convert text answer to option ID for consistent storage"""
        if not options or not text_or_id:
            return str(text_or_id) if text_or_id else ""
        # First check if it's already an ID
        for opt in options:
            if isinstance(opt, dict) and opt.get('id') == text_or_id:
                return text_or_id
        # Then check if it's text that matches an option
        for opt in options:
            if isinstance(opt, dict) and opt.get('text') == text_or_id:
                return opt.get('id', text_or_id)
        return str(text_or_id)

    # Save/update answers
    saved_count = 0
    for answer in data.answers:
        question = question_lookup.get(answer.question_id)
        if not question:
            continue

        # CRITICAL: Normalize the answer to option ID before saving
        normalized_answer = normalize_answer(question.options, answer.selected_option)

        # Check if answer already exists
        existing = await db.execute(
            select(UserAnswer).where(
                and_(
                    UserAnswer.attempt_id == attempt.id,
                    UserAnswer.question_id == answer.question_id
                )
            )
        )
        existing_answer = existing.scalar_one_or_none()

        if existing_answer:
            # Update existing answer with normalized value
            existing_answer.answer_text = normalized_answer
            existing_answer.time_spent_seconds = answer.time_spent_seconds
        else:
            # Create new answer with normalized value
            new_answer = UserAnswer(
                attempt_id=attempt.id,
                question_id=answer.question_id,
                answer_text=normalized_answer,
                is_correct=False,  # Will be calculated on final submit
                marks_obtained=0,
                time_spent_seconds=answer.time_spent_seconds
            )
            db.add(new_answer)
        saved_count += 1
    
    # Update tab switches
    attempt.tab_switches = data.tab_switches
    
    await db.commit()
    
    return {
        "success": True,
        "saved_count": saved_count,
        "saved_at": datetime.now(timezone.utc).isoformat()
    }


@router.post("/candidate/submit", response_model=AssessmentResultResponse)
async def submit_assessment(
    data: SubmitAssessmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit assessment and auto-evaluate.
    CRITICAL: This endpoint handles final submission with auto-save recovery.
    """
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"[SUBMIT] Starting: attempt_id={data.attempt_id}, user={current_user.id}, answers_count={len(data.answers)}")
        
        # ========== STEP 1: Validate attempt ==========
        result = await db.execute(
            select(TestAttempt).where(
                and_(
                    TestAttempt.id == data.attempt_id,
                    TestAttempt.user_id == current_user.id
                )
            )
        )
        attempt = result.scalar_one_or_none()
        
        if not attempt:
            logger.error(f"[SUBMIT] Attempt not found: {data.attempt_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attempt not found"
            )
        
        if attempt.status == "completed":
            logger.warning(f"[SUBMIT] Already completed: {data.attempt_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assessment already submitted"
            )
        
        # ========== STEP 2: Load assessment data ==========
        assessment = await get_assessment_or_404(db, attempt.test_id)
        
        if not assessment:
            logger.error(f"[SUBMIT] Assessment not found: {attempt.test_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assessment not found"
            )
        
        # ========== STEP 3: Build lookups ==========
        question_lookup = {}
        section_lookup = {}
        for section in assessment.sections:
            section_lookup[section.id] = section
            for q in section.questions:
                question_lookup[q.id] = q
        
        logger.info(f"[SUBMIT] Loaded {len(question_lookup)} questions from {len(section_lookup)} sections")
        
        # ========== STEP 4: Get pre-saved answers (CRITICAL for auto-save recovery) ==========
        existing_answers_result = await db.execute(
            select(UserAnswer).where(UserAnswer.attempt_id == attempt.id)
        )
        existing_answers = {ua.question_id: ua for ua in existing_answers_result.scalars().all()}
        logger.info(f"[SUBMIT] Found {len(existing_answers)} pre-saved answers")
        
        # ========== STEP 5: Merge answers (pre-saved + new from request) ==========
        all_answers = {}
        for qid, ua in existing_answers.items():
            all_answers[qid] = ua.answer_text
        
        for answer in data.answers:
            all_answers[answer.question_id] = answer.selected_option
        
        logger.info(f"[SUBMIT] Total merged answers: {len(all_answers)}")
        
        # ========== STEP 6: Helper functions ==========
        def get_option_text(options, option_id):
            """Get the text of an option by its ID"""
            if not options or not option_id:
                return str(option_id) if option_id else ""
            for opt in options:
                if isinstance(opt, dict) and opt.get('id') == option_id:
                    return opt.get('text', str(option_id))
            return str(option_id)

        def get_option_id(options, text_or_id):
            """Get the ID of an option by its text or ID"""
            if not options or not text_or_id:
                return str(text_or_id) if text_or_id else ""
            for opt in options:
                if isinstance(opt, dict) and opt.get('id') == text_or_id:
                    return text_or_id
            for opt in options:
                if isinstance(opt, dict) and opt.get('text') == text_or_id:
                    return opt.get('id', text_or_id)
            return str(text_or_id)

        # ========== STEP 7: Evaluate ALL answers ==========
        total_score = 0.0
        section_results = {}

        for question_id, selected_option in all_answers.items():
            question = question_lookup.get(question_id)

            # DEBUG: Log what we're comparing
            if question:
                logger.info(f"[EVAL] Q{question_id}: selected='{selected_option}', correct='{question.correct_answer}', options_type={type(question.options)}")
            if not question:
                logger.warning(f"[SUBMIT] Question not found: {question_id}")
                continue

            # Normalize answer
            selected_option_id = get_option_id(question.options, selected_option)

            # DEBUG: Log normalized value and comparison
            logger.info(f"[EVAL] Q{question_id}: normalized='{selected_option_id}' vs correct='{question.correct_answer}' => match={selected_option_id == question.correct_answer}")

            # Check correctness
            is_correct = (question.correct_answer or "") == selected_option_id
            marks_obtained = float(question.marks) if is_correct else 0.0
            total_score += marks_obtained

            # Update or create answer record
            if question_id in existing_answers:
                existing_answers[question_id].answer_text = selected_option_id
                existing_answers[question_id].is_correct = is_correct
                existing_answers[question_id].marks_obtained = marks_obtained
            else:
                user_answer = UserAnswer(
                    attempt_id=attempt.id,
                    question_id=question_id,
                    answer_text=selected_option_id,
                    is_correct=is_correct,
                    marks_obtained=marks_obtained,
                    time_spent_seconds=0
                )
                db.add(user_answer)

            # Build section result
            if question.section_id not in section_results:
                section = section_lookup.get(question.section_id)
                section_results[question.section_id] = {
                    "section_id": question.section_id,
                    "section_title": section.title if section else "Unknown",
                    "total_marks": 0.0,
                    "marks_obtained": 0.0,
                    "questions": []
                }

            user_answer_text = get_option_text(question.options, selected_option_id)
            correct_answer_text = get_option_text(question.options, question.correct_answer) if question.correct_answer else ""

            section_results[question.section_id]["marks_obtained"] += marks_obtained
            section_results[question.section_id]["total_marks"] += float(question.marks)
            section_results[question.section_id]["questions"].append({
                "question_id": question.id,
                "question_number": question.question_number or str(question.id),
                "question_text": question.question_text or "",
                "user_answer": user_answer_text,
                "correct_answer": correct_answer_text,
                "is_correct": is_correct,
                "marks_obtained": float(marks_obtained),
                "max_marks": float(question.marks),
            })

        logger.info(f"[SUBMIT] Evaluation complete: score={total_score}/{assessment.total_marks}")

        # ========== STEP 8: Update attempt status ==========
        now = datetime.now(timezone.utc)
        attempt.status = "completed"
        attempt.score = total_score
        attempt.percentage = (total_score / assessment.total_marks * 100) if assessment.total_marks > 0 else 0.0
        attempt.passed = total_score >= assessment.passing_marks
        attempt.completed_at = now
        attempt.time_taken_seconds = int((now - attempt.started_at).total_seconds()) if attempt.started_at else 0
        attempt.tab_switches = data.tab_switches

        if data.tab_switches > assessment.max_tab_switches_allowed:
            attempt.is_flagged = True
            attempt.flag_reason = f"Exceeded max tab switches: {data.tab_switches}/{assessment.max_tab_switches_allowed}"

        # ========== STEP 9: Commit and return ==========
        await db.commit()
        logger.info(f"[SUBMIT] SUCCESS: attempt_id={attempt.id}, score={total_score}, passed={attempt.passed}")

        return {
            "attempt_id": attempt.id,
            "assessment_id": assessment.id,
            "assessment_title": assessment.title or "",
            "category": assessment.category or "",
            "score": float(total_score),
            "total_marks": float(assessment.total_marks),
            "percentage": float(attempt.percentage),
            "passed": bool(attempt.passed),
            "time_taken_seconds": int(attempt.time_taken_seconds or 0),
            "completed_at": attempt.completed_at,
            "sections": list(section_results.values())
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log full traceback and return 500
        logger.error(f"[SUBMIT] CRITICAL ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit assessment: {str(e)}"
        )


@router.get("/candidate/results/{attempt_id}", response_model=AssessmentResultResponse)
async def get_assessment_result(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get assessment result for a completed attempt"""
    # Get attempt with answers
    result = await db.execute(
        select(TestAttempt)
        .options(selectinload(TestAttempt.answers))
        .where(
            and_(
                TestAttempt.id == attempt_id,
                TestAttempt.user_id == current_user.id,
                TestAttempt.status == "completed"
            )
        )
    )
    attempt = result.scalar_one_or_none()

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not found"
        )

    # Get assessment with sections
    assessment = await get_assessment_or_404(db, attempt.test_id)

    # Build question and section lookup
    question_lookup = {}
    section_lookup = {}
    for section in assessment.sections:
        section_lookup[section.id] = section
        for q in section.questions:
            question_lookup[q.id] = q

    # Helper to get option text from ID
    def get_option_text(options, option_id):
        """Get the text of an option by its ID"""
        if not options or not option_id:
            return option_id
        for opt in options:
            if isinstance(opt, dict) and opt.get('id') == option_id:
                return opt.get('text', option_id)
        return option_id  # Return ID if not found

    # Build results by section
    section_results = {}
    for answer in attempt.answers:
        question = question_lookup.get(answer.question_id)
        if not question:
            continue

        if question.section_id not in section_results:
            section = section_lookup.get(question.section_id)
            section_results[question.section_id] = {
                "section_id": question.section_id,
                "section_title": section.title if section else "Unknown",
                "total_marks": 0,
                "marks_obtained": 0,
                "questions": []
            }

        # Convert option IDs to text for display
        user_answer_text = get_option_text(question.options, answer.answer_text)
        correct_answer_text = get_option_text(question.options, question.correct_answer)

        section_results[question.section_id]["marks_obtained"] += answer.marks_obtained
        section_results[question.section_id]["total_marks"] += question.marks
        section_results[question.section_id]["questions"].append({
            "question_id": question.id,
            "question_number": question.question_number,
            "question_text": question.question_text,
            "user_answer": user_answer_text,
            "correct_answer": correct_answer_text,
            "is_correct": answer.is_correct,
            "marks_obtained": answer.marks_obtained,
            "max_marks": question.marks,
        })
    
    return {
        "attempt_id": attempt.id,
        "assessment_id": assessment.id,
        "assessment_title": assessment.title or "",
        "category": assessment.category or "",
        "score": float(attempt.score or 0),
        "total_marks": float(attempt.total_marks or 0),
        "percentage": float(attempt.percentage or 0),
        "passed": bool(attempt.passed),
        "time_taken_seconds": attempt.time_taken_seconds or 0,
        "completed_at": attempt.completed_at,
        "sections": list(section_results.values())
    }


@router.get("/candidate/history")
async def get_candidate_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all standalone assessment attempts for the current user (excludes job-linked tests)"""
    from ..models.job import Job
    
    # Get test IDs that are linked to jobs (these should NOT appear in assessment history)
    job_test_result = await db.execute(
        select(Job.test_id).where(Job.test_id.isnot(None))
    )
    job_test_ids = set(row[0] for row in job_test_result.all())
    
    # Get completed attempts excluding job tests
    result = await db.execute(
        select(TestAttempt)
        .where(
            and_(
                TestAttempt.user_id == current_user.id,
                TestAttempt.status == "completed",
                TestAttempt.test_id.notin_(job_test_ids) if job_test_ids else True
            )
        )
        .order_by(TestAttempt.completed_at.desc())
    )
    attempts = result.scalars().all()
    
    # Get test titles
    test_ids = list(set(a.test_id for a in attempts))
    if test_ids:
        tests_result = await db.execute(
            select(Test).where(Test.id.in_(test_ids))
        )
        tests = {t.id: t for t in tests_result.scalars().all()}
    else:
        tests = {}
    
    return [
        {
            "id": a.id,
            "test_id": a.test_id,
            "test_title": tests.get(a.test_id).title if tests.get(a.test_id) else f"Assessment #{a.test_id}",
            "status": a.status,
            "score": a.score or 0,
            "total_marks": tests.get(a.test_id).total_marks if tests.get(a.test_id) else 0,
            "percentage": a.percentage or 0,
            "passed": a.passed or False,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        }
        for a in attempts
    ]


# ========== Categories ==========

@router.get("/categories")
async def get_assessment_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all unique assessment categories"""
    result = await db.execute(
        select(Test.category)
        .where(
            and_(
                Test.assessment_type == "standalone_assessment",
                Test.category.isnot(None)
            )
        )
        .distinct()
    )
    categories = [row[0] for row in result.all() if row[0]]
    return {"categories": sorted(categories)}


# ========== Admin Results ==========

@router.get("/admin/results")
async def get_admin_assessment_results(
    assessment_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all assessment results for admin view"""
    require_admin(current_user)
    
    # Get all standalone assessment IDs
    tests_result = await db.execute(
        select(Test)
        .where(
            and_(
                Test.assessment_type == "standalone_assessment",
                Test.is_active == True
            )
        )
    )
    standalone_tests = {t.id: t for t in tests_result.scalars().all()}
    test_ids = list(standalone_tests.keys())
    
    if not test_ids:
        return []
    
    # Build query for attempts
    query = select(TestAttempt).where(
        and_(
            TestAttempt.test_id.in_(test_ids),
            TestAttempt.status == "completed"
        )
    )
    
    if assessment_id:
        query = query.where(TestAttempt.test_id == assessment_id)
    
    query = query.order_by(TestAttempt.completed_at.desc())
    
    result = await db.execute(query)
    attempts = result.scalars().all()
    
    # Get user info
    user_ids = list(set(a.user_id for a in attempts))
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = {u.id: u for u in users_result.scalars().all()}
    else:
        users = {}
    
    return [
        {
            "id": a.id,
            "assessment_id": a.test_id,
            "assessment_title": standalone_tests.get(a.test_id).title if standalone_tests.get(a.test_id) else "Unknown",
            "category": standalone_tests.get(a.test_id).category if standalone_tests.get(a.test_id) else None,
            "user_id": a.user_id,
            "user_name": users.get(a.user_id).name if users.get(a.user_id) else "Unknown",
            "user_email": users.get(a.user_id).email if users.get(a.user_id) else "Unknown",
            "score": a.score,
            "total_marks": a.total_marks,
            "percentage": a.percentage,
            "passed": a.passed,
            "time_taken_seconds": a.time_taken_seconds,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        }
        for a in attempts
    ]


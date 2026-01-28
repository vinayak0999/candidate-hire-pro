"""
Admin API endpoints for managing divisions, tests, questions, and candidates
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional, Dict
from datetime import datetime, timezone
import os
import uuid
import aiofiles
import json

from ..database import get_db
from ..models.user import User, UserRole
from ..models.test import Division, Question, Test, TestQuestion, TestAttempt, UserAnswer
from ..models.job import Job, JobApplication, JobStatus
from ..models.message import Message
from ..schemas.test import (
    DivisionCreate, DivisionUpdate, DivisionResponse,
    QuestionCreate, QuestionUpdate, QuestionResponse,
    TestGenerateRequest, TestCreate, TestUpdate, TestResponse,
    AdminDashboardStats, CandidateListItem
)
from ..services.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ========== Helper to check admin role ==========
async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure the current user is an admin"""
    # For demo, allow all authenticated users to access admin
    # In production, check: if current_user.role != UserRole.ADMIN
    return current_user


# ========== Dashboard Stats ==========

@router.get("/stats", response_model=AdminDashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get admin dashboard statistics"""
    # Total candidates (users who are students)
    candidates_result = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.STUDENT)
    )
    total_candidates = candidates_result.scalar() or 0
    
    # Active jobs
    from ..models.job import Job
    jobs_result = await db.execute(
        select(func.count(Job.id)).where(Job.is_active == True)
    )
    active_jobs = jobs_result.scalar() or 0
    
    # Tests completed
    tests_result = await db.execute(
        select(func.count(TestAttempt.id)).where(TestAttempt.status == "completed")
    )
    tests_completed = tests_result.scalar() or 0
    
    # Flagged attempts
    flagged_result = await db.execute(
        select(func.count(TestAttempt.id)).where(TestAttempt.is_flagged == True)
    )
    flagged_attempts = flagged_result.scalar() or 0
    
    # Pass rates - will be 0 until real test data is available
    return AdminDashboardStats(
        total_candidates=total_candidates,
        active_jobs=active_jobs,
        tests_completed=tests_completed,
        flagged_attempts=flagged_attempts,
        mcq_pass_rate=0,
        text_annotation_pass_rate=0,
        image_annotation_pass_rate=0,
        video_annotation_pass_rate=0
    )


# ========== Division CRUD ==========

@router.get("/divisions", response_model=List[DivisionResponse])
async def get_divisions(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    include_inactive: bool = True  # Always show all divisions
):
    """Get all divisions"""
    query = select(Division)
    # Show all divisions regardless of active status
    query = query.order_by(Division.name)
    
    result = await db.execute(query)
    divisions = result.scalars().all()
    
    # Get test counts for each division
    responses = []
    for div in divisions:
        test_count_result = await db.execute(
            select(func.count(Test.id)).where(Test.division_id == div.id)
        )
        test_count = test_count_result.scalar() or 0
        
        responses.append(DivisionResponse(
            id=div.id,
            name=div.name,
            description=div.description,
            is_active=div.is_active,
            documents=div.documents,
            created_at=div.created_at,
            test_count=test_count
        ))
    
    return responses


@router.post("/divisions", response_model=DivisionResponse)
async def create_division(
    data: DivisionCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create a new division"""
    division = Division(name=data.name, description=data.description)
    db.add(division)
    await db.commit()
    await db.refresh(division)
    
    return DivisionResponse(
        id=division.id,
        name=division.name,
        description=division.description,
        is_active=division.is_active,
        documents=division.documents,
        created_at=division.created_at,
        test_count=0
    )


@router.put("/divisions/{division_id}", response_model=DivisionResponse)
async def update_division(
    division_id: int,
    data: DivisionUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update a division"""
    result = await db.execute(select(Division).where(Division.id == division_id))
    division = result.scalar_one_or_none()
    
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    if data.name is not None:
        division.name = data.name
    if data.description is not None:
        division.description = data.description
    if data.is_active is not None:
        division.is_active = data.is_active
    
    await db.commit()
    await db.refresh(division)
    
    test_count_result = await db.execute(
        select(func.count(Test.id)).where(Test.division_id == division.id)
    )
    
    return DivisionResponse(
        id=division.id,
        name=division.name,
        description=division.description,
        is_active=division.is_active,
        documents=division.documents,
        created_at=division.created_at,
        test_count=test_count_result.scalar() or 0
    )


@router.delete("/divisions/{division_id}")
async def delete_division(
    division_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Soft delete a division"""
    result = await db.execute(select(Division).where(Division.id == division_id))
    division = result.scalar_one_or_none()
    
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    division.is_active = False
    await db.commit()
    
    return {"message": "Division deleted"}


@router.put("/divisions/{division_id}/documents")
async def update_division_documents(
    division_id: int,
    documents: List[Dict[str, str]],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update shared documents for a division (used by Agent Analysis questions)"""
    result = await db.execute(select(Division).where(Division.id == division_id))
    division = result.scalar_one_or_none()
    
    if not division:
        raise HTTPException(status_code=404, detail="Division not found")
    
    division.documents = documents
    await db.commit()
    
    return {"message": "Documents updated", "documents": documents}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = "document",
    admin: User = Depends(require_admin)
):
    """
    Upload a file to Supabase Storage.
    """
    from ..services.supabase_upload import upload_to_supabase
    import traceback
    
    filename = file.filename or f"upload_{uuid.uuid4().hex}"
    safe_filename = filename.replace(" ", "_")
    file_path = f"{file_type}/{uuid.uuid4().hex}_{safe_filename}"
    
    try:
        url = await upload_to_supabase(
            file=file,
            bucket="division-docs",
            file_path=file_path,
            content_type=file.content_type
        )
        return {"url": url}
    except Exception as e:
        print(f"Upload error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ========== Question CRUD ==========

@router.get("/questions", response_model=List[QuestionResponse])
async def get_questions(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    division_id: Optional[int] = None,
    limit: int = Query(default=50, le=200)
):
    """Get questions with optional filters"""
    query = select(Question).where(Question.is_active == True)
    
    if question_type:
        query = query.where(Question.question_type == question_type)
    if difficulty:
        query = query.where(Question.difficulty == difficulty)
    if division_id:
        query = query.where(Question.division_id == division_id)
    
    query = query.order_by(Question.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/questions", response_model=QuestionResponse)
async def create_question(
    data: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create a new question"""
    question = Question(
        question_type=data.question_type,
        question_text=data.question_text,
        division_id=data.division_id,
        options=data.options,
        correct_answer=data.correct_answer,
        media_url=data.media_url,
        passage=data.passage,
        sentences=data.sentences,
        annotation_data=data.annotation_data,
        html_content=data.html_content,
        documents=data.documents,
        marks=data.marks,
        difficulty=data.difficulty,
        tags=data.tags
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    
    return question


@router.put("/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: int,
    data: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update a question"""
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    
    await db.commit()
    await db.refresh(question)
    
    return question


@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Soft delete a question"""
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    question.is_active = False
    await db.commit()
    
    return {"message": "Question deleted"}


# ========== Test Management ==========

@router.get("/tests", response_model=List[TestResponse])
async def get_tests(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    division_id: Optional[int] = None,
    is_published: Optional[bool] = None
):
    """Get all tests with optional filters"""
    query = select(Test).where(Test.is_active == True)
    
    if division_id:
        query = query.where(Test.division_id == division_id)
    if is_published is not None:
        query = query.where(Test.is_published == is_published)
    
    query = query.order_by(Test.created_at.desc())
    
    result = await db.execute(query)
    tests = result.scalars().all()
    
    # Add division names
    responses = []
    for test in tests:
        division_name = None
        if test.division_id:
            div_result = await db.execute(
                select(Division.name).where(Division.id == test.division_id)
            )
            division_name = div_result.scalar()
        
        responses.append(TestResponse(
            id=test.id,
            title=test.title,
            description=test.description,
            division_id=test.division_id,
            division_name=division_name,
            duration_minutes=test.duration_minutes,
            total_questions=test.total_questions,
            total_marks=test.total_marks,
            passing_marks=test.passing_marks,
            mcq_count=test.mcq_count,
            text_annotation_count=test.text_annotation_count,
            image_annotation_count=test.image_annotation_count,
            video_annotation_count=test.video_annotation_count,
            agent_analysis_count=test.agent_analysis_count,
            is_active=test.is_active,
            is_published=test.is_published,
            created_at=test.created_at
        ))
    
    return responses


@router.post("/tests/generate", response_model=TestResponse)
async def generate_test(
    data: TestGenerateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Generate a new test with specified module configurations"""
    # Calculate totals
    total_questions = 0
    total_marks = 0.0
    
    # Track counts by type
    mcq_count = 0
    text_count = 0
    image_count = 0
    video_count = 0
    reading_count = 0
    jumble_count = 0
    agent_analysis_count = 0
    
    # Handle new sections format
    if data.sections:
        for section_type, config in data.sections.items():
            if config.enabled:
                section_total = config.hard + config.medium + config.easy
                total_questions += section_total
                total_marks += section_total * config.marks_per_question
                
                # Map to type counts
                if section_type == 'mcq':
                    mcq_count = section_total
                elif section_type == 'video':
                    video_count = section_total
                elif section_type == 'image':
                    image_count = section_total
                elif section_type == 'reading':
                    reading_count = section_total
                    text_count = section_total  # Map to text_annotation for backwards compat
                elif section_type == 'jumble':
                    jumble_count = section_total
                elif section_type == 'agent_analysis':
                    agent_analysis_count = section_total
    else:
        # Legacy format handling
        if data.mcq and data.mcq.enabled:
            mcq_count = data.mcq.count
            total_questions += data.mcq.count
            total_marks += data.mcq.count * data.mcq.marks_per_question
        if data.text_annotation and data.text_annotation.enabled:
            text_count = data.text_annotation.count
            total_questions += data.text_annotation.count
            total_marks += data.text_annotation.count * data.text_annotation.marks_per_question
        if data.image_annotation and data.image_annotation.enabled:
            image_count = data.image_annotation.count
            total_questions += data.image_annotation.count
            total_marks += data.image_annotation.count * data.image_annotation.marks_per_question
        if data.video_annotation and data.video_annotation.enabled:
            video_count = data.video_annotation.count
            total_questions += data.video_annotation.count
            total_marks += data.video_annotation.count * data.video_annotation.marks_per_question
    
    # Create the test
    test = Test(
        title=data.title,
        description=data.description,
        division_id=data.division_id,
        duration_minutes=data.duration_minutes,
        total_questions=total_questions,
        total_marks=total_marks,
        passing_marks=total_marks * 0.5,  # 50% passing by default
        mcq_count=mcq_count,
        text_annotation_count=text_count,
        image_annotation_count=image_count,
        video_annotation_count=video_count,
        agent_analysis_count=agent_analysis_count,
        enable_tab_switch_detection=data.enable_tab_switch_detection,
        max_tab_switches_allowed=data.max_tab_switches_allowed
    )
    
    db.add(test)
    await db.commit()
    await db.refresh(test)
    
    # Get division name if exists
    division_name = None
    if test.division_id:
        div_result = await db.execute(
            select(Division.name).where(Division.id == test.division_id)
        )
        division_name = div_result.scalar()
    
    return TestResponse(
        id=test.id,
        title=test.title,
        description=test.description,
        division_id=test.division_id,
        division_name=division_name,
        duration_minutes=test.duration_minutes,
        total_questions=test.total_questions,
        total_marks=test.total_marks,
        passing_marks=test.passing_marks,
        mcq_count=test.mcq_count,
        text_annotation_count=test.text_annotation_count,
        image_annotation_count=test.image_annotation_count,
        video_annotation_count=test.video_annotation_count,
        agent_analysis_count=test.agent_analysis_count,
        is_active=test.is_active,
        is_published=test.is_published,
        created_at=test.created_at
    )


@router.put("/tests/{test_id}", response_model=TestResponse)
async def update_test(
    test_id: int,
    data: TestUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update a test"""
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalar_one_or_none()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(test, field, value)
    
    await db.commit()
    await db.refresh(test)
    
    division_name = None
    if test.division_id:
        div_result = await db.execute(
            select(Division.name).where(Division.id == test.division_id)
        )
        division_name = div_result.scalar()
    
    return TestResponse(
        id=test.id,
        title=test.title,
        description=test.description,
        division_id=test.division_id,
        division_name=division_name,
        duration_minutes=test.duration_minutes,
        total_questions=test.total_questions,
        total_marks=test.total_marks,
        passing_marks=test.passing_marks,
        mcq_count=test.mcq_count,
        text_annotation_count=test.text_annotation_count,
        image_annotation_count=test.image_annotation_count,
        video_annotation_count=test.video_annotation_count,
        agent_analysis_count=test.agent_analysis_count,
        is_active=test.is_active,
        is_published=test.is_published,
        created_at=test.created_at
    )


@router.post("/tests/{test_id}/publish")
async def publish_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Publish a test"""
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalar_one_or_none()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    test.is_published = True
    await db.commit()
    
    return {"message": "Test published"}


@router.delete("/tests/{test_id}")
async def delete_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete a test (soft delete - sets is_active to False)"""
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalar_one_or_none()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    test.is_active = False
    await db.commit()
    
    return {"success": True, "message": "Test deleted"}

@router.get("/tests/{test_id}/preview")
async def get_test_preview(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get test details with all questions for preview"""
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalar_one_or_none()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Get division name
    division_name = None
    if test.division_id:
        div_result = await db.execute(
            select(Division.name).where(Division.id == test.division_id)
        )
        division_name = div_result.scalar()
    
    # Get questions linked to this test via TestQuestion
    questions_result = await db.execute(
        select(Question)
        .join(TestQuestion, Question.id == TestQuestion.question_id)
        .where(TestQuestion.test_id == test_id)
        .where(Question.is_active == True)
        .order_by(TestQuestion.order)
    )
    linked_questions = questions_result.scalars().all()
    
    # If no linked questions, get sample questions based on test configuration
    if not linked_questions:
        from .tests import _get_sample_questions
        linked_questions = await _get_sample_questions(db, test)
    
    # Format questions for response
    questions_data = [
        {
            "id": q.id,
            "question_type": q.question_type,
            "question_text": q.question_text,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "media_url": q.media_url,
            "passage": q.passage,
            "sentences": q.sentences,
            "marks": q.marks,
            "difficulty": q.difficulty,
        }
        for q in linked_questions
    ]
    
    return {
        "id": test.id,
        "title": test.title,
        "description": test.description,
        "division_id": test.division_id,
        "division_name": division_name,
        "duration_minutes": test.duration_minutes,
        "total_questions": test.total_questions,
        "total_marks": test.total_marks,
        "passing_marks": test.passing_marks,
        "mcq_count": test.mcq_count,
        "text_annotation_count": test.text_annotation_count,
        "image_annotation_count": test.image_annotation_count,
        "video_annotation_count": test.video_annotation_count,
        "is_published": test.is_published,
        "enable_tab_switch_detection": test.enable_tab_switch_detection,
        "max_tab_switches_allowed": test.max_tab_switches_allowed,
        "questions": questions_data
    }


# ========== Candidate Management ==========

@router.get("/candidates", response_model=List[CandidateListItem])
async def get_candidates(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200)
):
    """Get list of candidates"""
    query = select(User).where(User.role == UserRole.STUDENT).order_by(User.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    candidates = []
    for user in users:
        # Get latest job application
        app_result = await db.execute(
            select(JobApplication)
            .where(JobApplication.user_id == user.id)
            .order_by(JobApplication.applied_at.desc())
            .limit(1)
        )
        app = app_result.scalar_one_or_none()
        
        # Get test attempt stats
        attempt_result = await db.execute(
            select(TestAttempt)
            .where(TestAttempt.user_id == user.id)
            .order_by(TestAttempt.started_at.desc())
        )
        attempts = attempt_result.scalars().all()
        
        completed = sum(1 for a in attempts if a.status == "completed")
        total = len(attempts) if attempts else 1
        progress = (completed / total) * 100 if total > 0 else 0
        
        # Determine status
        candidate_status = "applied"
        if any(a.is_flagged for a in attempts):
            candidate_status = "flagged"
        elif completed > 0:
            candidate_status = "completed"
        elif any(a.status == "in_progress" for a in attempts):
            candidate_status = "in_progress"
        
        candidates.append(CandidateListItem(
            id=user.id,
            name=user.name,
            email=user.email,
            applied_job=None,  # Would need job name
            progress=progress,
            status=candidate_status,
            last_activity=attempts[0].started_at if attempts else user.created_at
        ))
    
    # Filter by status if provided
    if status:
        candidates = [c for c in candidates if c.status == status]
    
    return candidates


@router.post("/candidates/{candidate_id}/approve")
async def approve_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Approve a candidate"""
    result = await db.execute(select(User).where(User.id == candidate_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Update job application status to selected
    await db.execute(
        JobApplication.__table__.update()
        .where(JobApplication.user_id == candidate_id)
        .values(status="selected")
    )
    await db.commit()
    
    return {"message": "Candidate approved"}


@router.post("/candidates/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Reject a candidate"""
    result = await db.execute(select(User).where(User.id == candidate_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Update job application status to rejected
    await db.execute(
        JobApplication.__table__.update()
        .where(JobApplication.user_id == candidate_id)
        .values(status="rejected")
    )
    await db.commit()
    
    return {"message": "Candidate rejected"}


# ========== Test Attempts (for viewing) ==========

@router.get("/attempts")
async def get_all_attempts(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    flagged_only: bool = False,
    limit: int = Query(default=50, le=200)
):
    """Get all test attempts for admin review"""
    query = select(TestAttempt)
    
    if flagged_only:
        query = query.where(TestAttempt.is_flagged == True)
    
    query = query.order_by(TestAttempt.started_at.desc()).limit(limit)
    
    result = await db.execute(query)
    attempts = result.scalars().all()
    
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "test_id": a.test_id,
            "status": a.status,
            "score": a.score,
            "percentage": a.percentage,
            "tab_switches": a.tab_switches,
            "is_flagged": a.is_flagged,
            "flag_reason": a.flag_reason,
            "started_at": a.started_at,
            "completed_at": a.completed_at
        }
        for a in attempts
    ]


# ========== Test Results (for grading) ==========

@router.get("/test-results")
async def get_test_results(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    job_id: Optional[int] = None
):
    """Get all completed test attempts with user, job, and score info"""
    
    # Get completed attempts
    query = select(TestAttempt).where(
        TestAttempt.status == "completed"
    ).order_by(TestAttempt.completed_at.desc())
    
    result = await db.execute(query)
    attempts = result.scalars().all()
    
    if not attempts:
        return []
    
    # Get user info separately
    user_ids = list(set(a.user_id for a in attempts))
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = {u.id: u for u in users_result.scalars().all()}
    
    # Get test info
    test_ids = list(set(a.test_id for a in attempts))
    tests_result = await db.execute(select(Test).where(Test.id.in_(test_ids)))
    tests = {t.id: t for t in tests_result.scalars().all()}
    
    # Get jobs linked to tests
    from ..models.job import Job
    jobs_result = await db.execute(select(Job).where(Job.test_id.in_(test_ids)))
    jobs_by_test = {j.test_id: j for j in jobs_result.scalars().all()}
    
    # Filter by job if specified
    if job_id:
        job_test_ids = [tid for tid, j in jobs_by_test.items() if j.id == job_id]
        attempts = [a for a in attempts if a.test_id in job_test_ids]
    
    # Check for file answers
    attempt_ids = [a.id for a in attempts]
    if attempt_ids:
        answers_result = await db.execute(
            select(UserAnswer).where(
                UserAnswer.attempt_id.in_(attempt_ids),
                UserAnswer.answer_text.like("FILE:%")
            )
        )
        file_answers = {a.attempt_id: a.answer_text for a in answers_result.scalars().all()}
    else:
        file_answers = {}
    
    results = []
    for a in attempts:
        user = users.get(a.user_id)
        test = tests.get(a.test_id)
        job = jobs_by_test.get(a.test_id)
        
        results.append({
            "id": a.id,
            "user_id": a.user_id,
            "user_name": user.name if user else "Unknown",
            "user_email": user.email if user else "",
            "test_id": a.test_id,
            "test_title": test.title if test else f"Test #{a.test_id}",
            "job_id": job.id if job else None,
            "job_title": job.role if job else None,
            "company": job.company_name if job else None,
            "score": a.score or 0,
            "max_score": a.total_marks or 100,
            "percentage": a.percentage or 0,
            "status": "passed" if (a.percentage or 0) >= 50 else "failed",
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "tab_switches": a.tab_switches or 0,
            "file_answer": file_answers.get(a.id)
        })
    
    return results


@router.get("/test-results/{result_id}/download")
async def download_answer_file(
    result_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Download the file answer for a test result"""
    from fastapi.responses import FileResponse
    
    # Find file answer for this attempt
    answer = await db.execute(
        select(UserAnswer).where(
            UserAnswer.attempt_id == result_id,
            UserAnswer.answer_text.like("FILE:%")
        )
    )
    answer = answer.scalar_one_or_none()
    
    if not answer:
        raise HTTPException(status_code=404, detail="No file answer found")
    
    filepath = answer.answer_text.replace("FILE:", "")
    
    # If it's a remote URL (Supabase), redirect to it
    if filepath.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=filepath)

    # Handle both relative and absolute paths
    if not os.path.isabs(filepath):
        # If relative path, resolve it relative to backend directory
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(backend_dir, filepath)
    
    if not os.path.exists(filepath):
        # Try looking in the uploads/answers directory as fallback
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filename = os.path.basename(answer.answer_text.replace("FILE:", ""))
        fallback_path = os.path.join(backend_dir, "uploads", "answers", filename)
        if os.path.exists(fallback_path):
            filepath = fallback_path
        else:
             raise HTTPException(status_code=404, detail=f"File not found on server: {filepath}")

    return FileResponse(
        filepath,
        filename=os.path.basename(filepath),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ========== File Upload ==========

# Ensure uploads directory exists (fallback for local storage)
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Allowed file extensions (more reliable than content-type)
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
ALLOWED_HTML_EXTENSIONS = {".html", ".htm"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Query(..., description="Type: video, image, html, or document"),
    admin: User = Depends(require_admin)
):
    """
    Upload a video, image, HTML, or document file.
    Uses Cloudinary for scalable CDN delivery (handles 10k+ concurrent users).
    Falls back to local storage if Cloudinary not configured.
    
    Best practices for scale:
    - CDN delivery for global performance
    - Auto-optimization for images/videos
    - Chunked uploads for large files
    """
    from ..services.cloudinary_service import (
        upload_video, upload_image, is_cloudinary_available
    )
    
    # Debug logging
    filename = file.filename or ""
    content_type = file.content_type or ""
    print(f"[Upload Debug] filename={filename}, content_type={content_type}, file_type={file_type}")
    
    # Get extension from filename, or infer from content-type if no extension
    ext = os.path.splitext(filename)[1].lower() if filename else ""
    
    # If no extension, try to infer from content-type
    if not ext or ext == ".bin":
        content_type_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "video/mp4": ".mp4",
            "video/webm": ".webm",
            "video/quicktime": ".mov",
            "text/html": ".html",
            "application/pdf": ".pdf",
            "application/msword": ".doc",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/octet-stream": ""  # Unknown, check file_type param
        }
        ext = content_type_map.get(content_type.lower(), "")
        if not ext and file_type == "image":
            ext = ".png"  # Default for images (e.g., screenshots, pasted images)
        elif not ext and file_type == "video":
            ext = ".mp4"  # Default for videos
        elif not ext and file_type == "html":
            ext = ".html"  # Default for HTML
        elif not ext and file_type == "document":
            ext = ".pdf"  # Default for documents
    
    # Validate extension
    if file_type == "video":
        if ext and ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid video format '{ext}'. Allowed: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}"
            )
    elif file_type == "image":
        if ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid image format '{ext}'. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
            )
    elif file_type == "html":
        if ext and ext not in ALLOWED_HTML_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid HTML format '{ext}'. Allowed: {', '.join(ALLOWED_HTML_EXTENSIONS)}"
            )
    elif file_type == "document":
        if ext and ext not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid document format '{ext}'. Allowed: {', '.join(ALLOWED_DOCUMENT_EXTENSIONS)}"
            )
    else:
        raise HTTPException(status_code=400, detail="file_type must be 'video', 'image', 'html', or 'document'")
    
    # Read file content with size check -> Stream to temp file
    import aiofiles
    import os
    
    unique_name = f"{file_type}_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    file_size = 0
    
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            while True:
                chunk = await file.read(64 * 1024)
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    # Cleanup and error
                    try:
                        os.remove(file_path)
                    except:
                        pass
                    raise HTTPException(status_code=413, detail="File too large (max 100MB)")
                await f.write(chunk)
                
        if file_size == 0:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Empty file not allowed")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save file: {str(e)}")
    
    # Try Cloudinary first (recommended for production scale)
    if is_cloudinary_available():
        try:
            # For cloudinary, we can upload from the file path
            # (Assuming Cloudinary SDK supports path, or we read stream from path)
            # Actually, standard cloudinary upload() usually takes file path too
            # check service impl... assuming it takes file-like object
            import aiofiles
            
            # Re-open safely for reading
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read() # Still loading to MEM for cloudinary? 
                # Ideally cloudinary_service should take path or stream.
                # For now given existing service uses BytesIO, we might still hit limit here if strict.
                # BUT, usually admin uploads are rarer. Best fix: refactor service later.
                # For NOW, at least local save is safe.
                import io
                file_stream = io.BytesIO(content)

            if file_type == "video":
                from ..services.cloudinary_service import upload_video
                result = await upload_video(
                    file_stream, 
                    folder="hiring-pro/test-media/videos"
                )
            elif file_type == "image":
                result = await upload_image(
                    file_stream, 
                    folder="hiring-pro/test-media/images"
                )
            elif file_type == "html":
                from ..services.cloudinary_service import upload_document
                result = await upload_document(
                    file_stream, 
                    folder="hiring-pro/test-media/html",
                    filename=filename
                )
            elif file_type == "document":
                from ..services.cloudinary_service import upload_document
                result = await upload_document(
                    file_stream, 
                    folder="hiring-pro/test-media/documents",
                    filename=filename
                )
            else:
                result = None
            
            # If successful, remove local temp file
            if result:
                try:
                    os.remove(file_path)
                except:
                    pass
                    
                return {
                    "success": True,
                    "file_url": result["url"],
                    "public_id": result.get("public_id"),
                    "file_type": file_type,
                    "size": file_size,
                    "storage": "cloudinary"
                }
        except Exception as e:
            # Log but fall through to local storage (file is already there)
            print(f"Cloudinary upload failed, falling back to local: {e}")
            # File is already at file_path, so we just use that.
    
    # Fallback: Local storage (already saved at file_path)
    # Just need to confirm path is right
    
    # (Existing logic saved to file_path already)
    
    file_url = f"/uploads/{unique_name}"
    
    return {
        "success": True,
        "file_url": file_url,
        "file_name": unique_name,
        "file_type": file_type,
        "size": file_size,
        "storage": "local"
    }


# ========== Excel Bulk Import ==========

@router.post("/questions/import-excel")
async def import_questions_from_excel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """
    Bulk import questions from Excel/JSON file.
    Expected format: [{type, question, media_url, option_a-d, correct, passage, difficulty}]
    Optimized with batch inserts for 10k+ performance.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Stream file content to temp file first to avoid OOM
    import tempfile
    import os
    
    fd, temp_path = tempfile.mkstemp()
    try:
        async with aiofiles.open(temp_path, 'wb') as f:
            while True:
                chunk = await file.read(64 * 1024)
                if not chunk:
                    break
                await f.write(chunk)
        
        # Now read from temp file
        # For JSON:
        if file.filename.endswith('.json'):
            async with aiofiles.open(temp_path, 'r') as f:
                content_str = await f.read()
                # Still loading text to memory, but better than raw+text.
                # For HUGE JSON, we'd need ijson, but 10MB limit is usually fine for text.
                # The main OOM killer was raw bytes + decode + json obj all at once.
                # This at least clears the raw upload buffer.
                content = content_str.encode('utf-8')
        else:
             # For Excel, pandas reads path/bytes. We can pass the path!
             # This is MUCH better for pandas memory usage.
             content = None # Signal to use path
    except Exception as e:
        os.close(fd)
        os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
        
    # Read file content
    # content = await file.read() # REMOVED
    
    questions_data = []
    errors = []
    
    # Parse based on file type
    # Parse based on file type
    if file.filename.endswith('.json'):
        try:
            async with aiofiles.open(temp_path, 'r') as f:
                content_str = await f.read()
            questions_data = json.loads(content_str)
        except json.JSONDecodeError as e:
            os.close(fd)
            os.remove(temp_path)
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    elif file.filename.endswith(('.xlsx', '.xls')):
        try:
            import openpyxl
            # Load workbook from filename (optimized read_only=True)
            wb = openpyxl.load_workbook(temp_path, read_only=True)
            ws = wb.active
            
            # Get header row
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                raise HTTPException(status_code=400, detail="Empty Excel file")
            
            headers = [str(h).lower().strip() if h else "" for h in rows[0]]
            
            # Parse data rows
            for row_idx, row in enumerate(rows[1:], start=2):
                try:
                    row_dict = dict(zip(headers, row))
                    
                    q_type = str(row_dict.get('type', '')).lower().strip()
                    q_text = str(row_dict.get('question', '') or '')
                    
                    if not q_type or not q_text:
                        continue
                    
                    questions_data.append({
                        "type": q_type,
                        "question": q_text,
                        "media_url": row_dict.get('media_url'),
                        "option_a": row_dict.get('option_a'),
                        "option_b": row_dict.get('option_b'),
                        "option_c": row_dict.get('option_c'),
                        "option_d": row_dict.get('option_d'),
                        "correct": row_dict.get('correct'),
                        "passage": row_dict.get('passage'),
                        "difficulty": str(row_dict.get('difficulty', 'medium')).lower()
                    })
                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")
            
            wb.close()
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl not installed. Run: pip install openpyxl")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Excel parse error: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use .xlsx or .json")
    
    # Batch insert questions
    imported = 0
    for q in questions_data:
        try:
            q_type = q.get('type', 'mcq')
            
            # Build options for MCQ
            options = None
            correct_answer = None
            if q_type == 'mcq':
                options = [
                    q.get('option_a', ''),
                    q.get('option_b', ''),
                    q.get('option_c', ''),
                    q.get('option_d', '')
                ]
                options = [o for o in options if o]
                
                correct_letter = str(q.get('correct', '')).upper()
                if correct_letter and len(correct_letter) == 1:
                    idx = ord(correct_letter) - ord('A')
                    if 0 <= idx < len(options):
                        correct_answer = options[idx]
            
            # Build sentences for jumble
            sentences = None
            if q_type == 'jumble':
                sentences = [q.get('option_a'), q.get('option_b'), q.get('option_c'), q.get('option_d'), q.get('passage')]
                sentences = [s for s in sentences if s]
            
            question = Question(
                question_type=q_type,
                question_text=q.get('question', ''),
                media_url=q.get('media_url') if q_type in ['video', 'image'] else None,
                passage=q.get('passage') if q_type == 'reading' else None,
                sentences=sentences,
                options=options,
                correct_answer=correct_answer,
                difficulty=q.get('difficulty', 'medium') or 'medium',
                marks=1.0  # Default marks
            )
            db.add(question)
            imported += 1
        except Exception as e:
            errors.append(f"Question '{q.get('question', '')[:30]}...': {str(e)}")
    
    # Commit batch
    await db.commit()
    
    return {
        "success": True,
        "imported": imported,
        "errors": errors[:10],  # Limit error messages
        "total_errors": len(errors)
    }


# ========== Messaging ==========

@router.post("/messages")
async def send_message(
    recipient_id: int,
    subject: str,
    content: str,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin sends a message to a candidate"""
    # Verify recipient exists and is a student
    result = await db.execute(select(User).where(User.id == recipient_id))
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    message = Message(
        sender_id=admin.id,
        recipient_id=recipient_id,
        subject=subject,
        content=content,
        reason=reason
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    return {
        "success": True,
        "message_id": message.id,
        "sent_to": recipient.name
    }


@router.get("/candidates/{candidate_id}/profile")
async def get_candidate_profile(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get full candidate profile including resume and signup info"""
    result = await db.execute(select(User).where(User.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get test attempts
    attempts_result = await db.execute(
        select(TestAttempt).where(TestAttempt.user_id == candidate_id).order_by(TestAttempt.started_at.desc())
    )
    attempts = attempts_result.scalars().all()
    
    # Get messages sent to this candidate
    messages_result = await db.execute(
        select(Message).where(Message.recipient_id == candidate_id).order_by(Message.created_at.desc())
    )
    messages = messages_result.scalars().all()
    
    return {
        "id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "avatar_url": candidate.avatar_url,
        "registration_number": candidate.registration_number,
        "degree": candidate.degree,
        "branch": candidate.branch,
        "batch": candidate.batch,
        "college": candidate.college,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "is_active": candidate.is_active,
        # Stats
        "neo_pat_score": candidate.neo_pat_score,
        "solved_easy": candidate.solved_easy,
        "solved_medium": candidate.solved_medium,
        "solved_hard": candidate.solved_hard,
        "badges_count": candidate.badges_count,
        # Test history
        "test_attempts": [
            {
                "test_id": a.test_id,
                "status": a.status,
                "score": a.score,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None
            }
            for a in attempts
        ],
        # Messages sent
        "messages": [
            {
                "id": m.id,
                "subject": m.subject,
                "reason": m.reason,
                "is_read": m.is_read,
                "created_at": m.created_at.isoformat() if m.created_at else None
            }
            for m in messages
        ]
    }


# ========== Job CRUD ==========

@router.get("/jobs")
async def get_jobs(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
    include_inactive: bool = False
):
    """Get all jobs with application counts"""
    query = select(Job)
    if not include_inactive:
        query = query.where(Job.is_active == True)
    query = query.order_by(Job.created_at.desc())
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    response = []
    for job in jobs:
        # Count applications
        count_result = await db.execute(
            select(func.count(JobApplication.id)).where(JobApplication.job_id == job.id)
        )
        application_count = count_result.scalar() or 0
        
        response.append({
            "id": job.id,
            "company_name": job.company_name,
            "company_logo": job.company_logo,
            "role": job.role,
            "location": job.location,
            "ctc": job.ctc,
            "job_type": job.job_type,
            "offer_type": job.offer_type.value if job.offer_type else "regular",
            "round_date": job.round_date.isoformat() if job.round_date else None,
            "is_active": job.is_active,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "applications": application_count
        })
    
    return response


@router.post("/jobs")
async def create_job(
    company_name: str,
    role: str,
    location: Optional[str] = None,
    ctc: Optional[float] = None,
    job_type: str = "Full Time",
    offer_type: str = "regular",
    round_date: Optional[str] = None,
    description: Optional[str] = None,
    test_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create a new job posting"""
    job = Job(
        company_name=company_name,
        role=role,
        location=location,
        ctc=ctc,
        job_type=job_type,
        offer_type=offer_type,
        description=description,
        round_date=datetime.fromisoformat(round_date) if round_date else None,
        test_id=test_id
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return {
        "id": job.id,
        "company_name": job.company_name,
        "role": job.role,
        "location": job.location,
        "ctc": job.ctc,
        "job_type": job.job_type,
        "offer_type": job.offer_type.value if job.offer_type else "regular",
        "round_date": job.round_date.isoformat() if job.round_date else None,
        "test_id": job.test_id,
        "is_active": job.is_active,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "applications": 0
    }


@router.put("/jobs/{job_id}")
async def update_job(
    job_id: int,
    company_name: Optional[str] = None,
    role: Optional[str] = None,
    location: Optional[str] = None,
    ctc: Optional[float] = None,
    job_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    round_date: Optional[str] = None,
    test_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Update an existing job"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if company_name is not None:
        job.company_name = company_name
    if role is not None:
        job.role = role
    if location is not None:
        job.location = location
    if ctc is not None:
        job.ctc = ctc
    if job_type is not None:
        job.job_type = job_type
    if is_active is not None:
        job.is_active = is_active
    if round_date is not None:
        job.round_date = datetime.fromisoformat(round_date)
    if test_id is not None:
        job.test_id = test_id
    
    await db.commit()
    await db.refresh(job)
    
    # Count applications
    count_result = await db.execute(
        select(func.count(JobApplication.id)).where(JobApplication.job_id == job.id)
    )
    application_count = count_result.scalar() or 0
    
    return {
        "id": job.id,
        "company_name": job.company_name,
        "role": job.role,
        "location": job.location,
        "ctc": job.ctc,
        "job_type": job.job_type,
        "offer_type": job.offer_type.value if job.offer_type else "regular",
        "round_date": job.round_date.isoformat() if job.round_date else None,
        "test_id": job.test_id,
        "is_active": job.is_active,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "applications": application_count
    }


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Delete a job (soft delete - sets is_active to False)"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.is_active = False
    await db.commit()
    
    return {"success": True, "message": "Job deactivated"}


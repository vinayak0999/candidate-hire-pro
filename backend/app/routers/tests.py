"""
Test Engine API endpoints for candidates to take tests
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime, timezone

from ..database import get_db
from ..models.user import User
from ..models.test import Test, TestQuestion, Question, TestAttempt, UserAnswer
from ..schemas.test import (
    StartTestRequest, SubmitAnswerRequest, CompleteTestRequest,
    TestAttemptResponse, TestSessionResponse, TestResultResponse,
    QuestionForTest
)
from ..services.auth import get_current_user

router = APIRouter(prefix="/api/tests", tags=["Test Engine"])


@router.get("/available")
async def get_available_tests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all available tests for the current user"""
    result = await db.execute(
        select(Test)
        .where(Test.is_active == True)
        .where(Test.is_published == True)
        .order_by(Test.created_at.desc())
    )
    tests = result.scalars().all()
    
    # Get user's attempts for each test
    test_data = []
    for test in tests:
        attempt_result = await db.execute(
            select(TestAttempt)
            .where(TestAttempt.test_id == test.id)
            .where(TestAttempt.user_id == current_user.id)
            .order_by(TestAttempt.started_at.desc())
            .limit(1)
        )
        attempt = attempt_result.scalar_one_or_none()
        
        test_data.append({
            "id": test.id,
            "title": test.title,
            "description": test.description,
            "duration_minutes": test.duration_minutes,
            "total_questions": test.total_questions,
            "total_marks": test.total_marks,
            "has_attempted": attempt is not None,
            "attempt_status": attempt.status if attempt else None,
            "last_score": attempt.score if attempt else None,
            "last_percentage": attempt.percentage if attempt else None
        })
    
    return test_data


@router.post("/start", response_model=TestSessionResponse)
async def start_test(
    data: StartTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start a new test session"""
    # Get the test
    result = await db.execute(
        select(Test)
        .where(Test.id == data.test_id)
        .where(Test.is_active == True)
        .where(Test.is_published == True)
    )
    test = result.scalar_one_or_none()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found or not available")
    
    # Check if user already COMPLETED this test (prevent retake)
    completed_result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.test_id == data.test_id)
        .where(TestAttempt.user_id == current_user.id)
        .where(TestAttempt.status == "completed")
    )
    completed_attempt = completed_result.scalar_one_or_none()
    
    if completed_attempt:
        raise HTTPException(
            status_code=400, 
            detail="You have already completed this test. Each test can only be taken once."
        )
    
    # Check if user has an in-progress attempt (to resume)
    existing_result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.test_id == data.test_id)
        .where(TestAttempt.user_id == current_user.id)
        .where(TestAttempt.status == "in_progress")
        .order_by(TestAttempt.started_at.desc())
        .limit(1)
    )
    existing_attempt = existing_result.scalar_one_or_none()
    
    if existing_attempt:
        # Resume existing attempt
        attempt = existing_attempt
    else:
        # Create new attempt
        attempt = TestAttempt(
            user_id=current_user.id,
            test_id=test.id,
            total_marks=test.total_marks
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)
    
    # Get questions for this test
    questions_result = await db.execute(
        select(Question)
        .join(TestQuestion, Question.id == TestQuestion.question_id)
        .where(TestQuestion.test_id == test.id)
        .order_by(TestQuestion.order)
    )
    questions = questions_result.scalars().all()
    
    # If no questions linked yet, get questions based on test config
    if not questions:
        # For demo, generate some sample MCQ questions
        questions = await _get_sample_questions(db, test)
    
    # Get division documents for agent_analysis questions
    division_docs = None
    if test.division_id:
        from ..models.test import Division
        div_result = await db.execute(
            select(Division).where(Division.id == test.division_id)
        )
        division = div_result.scalar_one_or_none()
        if division and division.documents:
            division_docs = division.documents
    
    # Convert to response format (without correct answers)
    question_responses = [
        QuestionForTest(
            id=q.id,
            question_type=q.question_type,
            question_text=q.question_text,
            options=q.options,
            media_url=q.media_url,
            passage=q.passage,
            sentences=q.sentences,
            html_content=q.html_content,
            # For agent_analysis, use division docs; otherwise use question docs
            documents=division_docs if q.question_type == "agent_analysis" and division_docs else q.documents,
            marks=q.marks
        )
        for q in questions
    ]
    
    return TestSessionResponse(
        attempt_id=attempt.id,
        test_id=test.id,
        test_title=test.title,
        duration_minutes=test.duration_minutes,
        total_questions=len(question_responses),
        questions=question_responses,
        started_at=attempt.started_at,
        enable_tab_switch_detection=test.enable_tab_switch_detection,
        max_tab_switches_allowed=test.max_tab_switches_allowed
    )


@router.get("/{test_id}/session", response_model=Optional[TestSessionResponse])
async def get_test_session(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resume an existing test session if it exists"""
    # Check if user has an in-progress attempt
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.test_id == test_id)
        .where(TestAttempt.user_id == current_user.id)
        .where(TestAttempt.status == "in_progress")
    )
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        return None
        
    # Get test info
    test_result = await db.execute(select(Test).where(Test.id == test_id))
    test = test_result.scalar_one_or_none()
    if not test:
        return None
        
    # Get questions
    questions_result = await db.execute(
        select(Question)
        .join(TestQuestion, Question.id == TestQuestion.question_id)
        .where(TestQuestion.test_id == test.id)
        .order_by(TestQuestion.order)
    )
    questions = questions_result.scalars().all()
    
    if not questions:
        questions = await _get_sample_questions(db, test)
    
    # Get division documents for agent_analysis questions
    division_docs = None
    if test.division_id:
        from ..models.test import Division
        div_result = await db.execute(
            select(Division).where(Division.id == test.division_id)
        )
        division = div_result.scalar_one_or_none()
        if division and division.documents:
            division_docs = division.documents
    
    question_responses = [
        QuestionForTest(
            id=q.id,
            question_type=q.question_type,
            question_text=q.question_text,
            options=q.options,
            media_url=q.media_url,
            passage=q.passage,
            sentences=q.sentences,
            html_content=q.html_content,
            # For agent_analysis, use division docs; otherwise use question docs
            documents=division_docs if q.question_type == "agent_analysis" and division_docs else q.documents,
            marks=q.marks
        )
        for q in questions
    ]
    
    return TestSessionResponse(
        attempt_id=attempt.id,
        test_id=test.id,
        test_title=test.title,
        duration_minutes=test.duration_minutes,
        total_questions=len(question_responses),
        questions=question_responses,
        started_at=attempt.started_at,
        enable_tab_switch_detection=test.enable_tab_switch_detection,
        max_tab_switches_allowed=test.max_tab_switches_allowed
    )


async def _get_sample_questions(db: AsyncSession, test: Test) -> List[Question]:
    """Get sample questions based on test configuration"""
    questions = []
    
    if test.mcq_count > 0:
        result = await db.execute(
            select(Question)
            .where(Question.question_type == "mcq")
            .where(Question.is_active == True)
            .limit(test.mcq_count)
        )
        questions.extend(result.scalars().all())
    
    if test.text_annotation_count > 0:
        # Match both "text" and "text_annotation" types
        result = await db.execute(
            select(Question)
            .where(Question.question_type.in_(["text_annotation", "text", "reading"]))
            .where(Question.is_active == True)
            .limit(test.text_annotation_count)
        )
        questions.extend(result.scalars().all())
    
    if test.image_annotation_count > 0:
        # Match both "image" and "image_annotation" types
        result = await db.execute(
            select(Question)
            .where(Question.question_type.in_(["image_annotation", "image"]))
            .where(Question.is_active == True)
            .limit(test.image_annotation_count)
        )
        questions.extend(result.scalars().all())
    
    if test.video_annotation_count > 0:
        # Match both "video" and "video_annotation" types
        result = await db.execute(
            select(Question)
            .where(Question.question_type.in_(["video_annotation", "video"]))
            .where(Question.is_active == True)
            .limit(test.video_annotation_count)
        )
        questions.extend(result.scalars().all())
    
    if test.agent_analysis_count > 0:
        result = await db.execute(
            select(Question)
            .where(Question.question_type == "agent_analysis")
            .where(Question.is_active == True)
            .where(Question.html_content.isnot(None))  # Only questions with content
            .order_by(Question.id.desc())  # Prefer newer questions
            .limit(test.agent_analysis_count)
        )
        questions.extend(result.scalars().all())
    
    return questions


@router.post("/submit-answer")
async def submit_answer(
    attempt_id: int,
    data: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit an answer for a question"""
    # Verify attempt belongs to user
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == current_user.id)
        .where(TestAttempt.status == "in_progress")
    )
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found or already completed")
    
    # Get the question
    q_result = await db.execute(
        select(Question).where(Question.id == data.question_id)
    )
    question = q_result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    # Check if answer already exists
    existing_result = await db.execute(
        select(UserAnswer)
        .where(UserAnswer.attempt_id == attempt_id)
        .where(UserAnswer.question_id == data.question_id)
    )
    existing_answer = existing_result.scalar_one_or_none()
    
    if existing_answer:
        # Update existing answer
        existing_answer.answer_text = data.answer_text
        existing_answer.annotation_data = data.annotation_data
        existing_answer.time_spent_seconds = data.time_spent_seconds
        existing_answer.answered_at = datetime.now(timezone.utc)
        
        # Auto-score for MCQ
        if question.question_type == "mcq" and question.correct_answer:
            existing_answer.is_correct = (data.answer_text == question.correct_answer)
            existing_answer.marks_obtained = question.marks if existing_answer.is_correct else 0
        
        await db.commit()
        return {"message": "Answer updated", "answer_id": existing_answer.id}
    else:
        # Create new answer
        is_correct = None
        marks_obtained = 0
        
        # Auto-score for MCQ
        if question.question_type == "mcq" and question.correct_answer:
            is_correct = (data.answer_text == question.correct_answer)
            marks_obtained = question.marks if is_correct else 0
        
        answer = UserAnswer(
            attempt_id=attempt_id,
            question_id=data.question_id,
            answer_text=data.answer_text,
            annotation_data=data.annotation_data,
            is_correct=is_correct,
            marks_obtained=marks_obtained,
            time_spent_seconds=data.time_spent_seconds
        )
        db.add(answer)
        await db.commit()
        await db.refresh(answer)
        
        # Update current question in attempt
        attempt.current_question += 1
        await db.commit()
        
        return {"message": "Answer submitted", "answer_id": answer.id}


@router.post("/upload-answer-file")
async def upload_answer_file(
    file: UploadFile = File(...),
    attempt_id: int = Form(...),
    question_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload Excel/CSV file as answer for agent_analysis questions"""
    import os
    from datetime import datetime
    from ..services.supabase_upload import upload_to_supabase
    
    # Verify attempt belongs to user
    attempt = await db.execute(
        select(TestAttempt).where(
            TestAttempt.id == attempt_id,
            TestAttempt.user_id == current_user.id
        )
    )
    attempt = attempt.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    
    # Validate file type
    allowed_extensions = {'.xlsx', '.xls', '.csv'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Only Excel (.xlsx, .xls) and CSV files allowed")
    
    # Build file path
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{attempt_id}_{question_id}_{timestamp}{ext}"
    safe_filename = filename.replace(" ", "_")
    file_path = f"answers/{safe_filename}"
    
    # Upload using the proper service
    try:
        public_url = await upload_to_supabase(
            file=file,
            bucket="division-docs",
            file_path=file_path,
            content_type=file.content_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    
    # Store file URL as answer
    answer = await db.execute(
        select(UserAnswer).where(
            UserAnswer.attempt_id == attempt_id,
            UserAnswer.question_id == question_id
        )
    )
    answer = answer.scalar_one_or_none()
    
    if answer:
        answer.answer_text = f"FILE:{public_url}"
    else:
        answer = UserAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            answer_text=f"FILE:{public_url}"
        )
        db.add(answer)
    
    await db.commit()
    
    return {"message": "File uploaded", "filepath": public_url}


@router.post("/complete/{attempt_id}", response_model=TestResultResponse)
async def complete_test(
    attempt_id: int,
    data: Optional[CompleteTestRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Complete a test and get results"""
    # Verify attempt belongs to user
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == current_user.id)
    )
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    
    if attempt.status == "completed":
        raise HTTPException(status_code=400, detail="Test already completed")
        
    # Update tab switches if provided
    if data and data.tab_switches:
        attempt.tab_switches = max(attempt.tab_switches, data.tab_switches)
        if attempt.tab_switches >= 3: # Should use test config here but simpler to hardcode default for now
             attempt.is_flagged = True
             attempt.flag_reason = f"Multiple tab switches: {attempt.tab_switches}"
    
    # Get the test
    test_result = await db.execute(
        select(Test).where(Test.id == attempt.test_id)
    )
    test = test_result.scalar_one_or_none()
    
    # Calculate score from all answers
    answers_result = await db.execute(
        select(UserAnswer).where(UserAnswer.attempt_id == attempt_id)
    )
    answers = answers_result.scalars().all()
    
    total_score = sum(a.marks_obtained for a in answers)
    total_marks = attempt.total_marks or test.total_marks
    percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
    passed = percentage >= 50  # 50% passing
    
    # Update attempt
    now = datetime.now(timezone.utc)
    attempt.status = "completed"
    attempt.score = total_score
    attempt.percentage = percentage
    attempt.passed = passed
    attempt.completed_at = now
    # Handle timezone-naive started_at from SQLite
    started_at = attempt.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    attempt.time_taken_seconds = int((now - started_at).total_seconds())
    
    await db.commit()
    await db.refresh(attempt)
    
    # Build answer details - fetch all questions in ONE query (avoid N+1)
    question_ids = [a.question_id for a in answers]
    if question_ids:
        questions_result = await db.execute(
            select(Question).where(Question.id.in_(question_ids))
        )
        questions_map = {q.id: q for q in questions_result.scalars().all()}
    else:
        questions_map = {}
    
    answer_details = []
    for answer in answers:
        question = questions_map.get(answer.question_id)
        answer_details.append({
            "question_id": answer.question_id,
            "question_text": question.question_text if question else "",
            "user_answer": answer.answer_text,
            "correct_answer": question.correct_answer if question else None,
            "is_correct": answer.is_correct,
            "marks_obtained": answer.marks_obtained,
            "max_marks": question.marks if question else 0
        })
    
    return TestResultResponse(
        attempt_id=attempt.id,
        test_id=attempt.test_id,
        test_title=test.title if test else "Unknown",
        score=attempt.score,
        total_marks=total_marks,
        percentage=attempt.percentage,
        passed=attempt.passed,
        time_taken_seconds=attempt.time_taken_seconds or 0,
        completed_at=attempt.completed_at,
        answers=answer_details
    )


@router.post("/flag-violation/{attempt_id}")
async def flag_violation(
    attempt_id: int,
    violation_type: str,  # "tab_switch", "fullscreen_exit", "copy_paste"
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Record a cheating violation"""
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == current_user.id)
        .where(TestAttempt.status == "in_progress")
    )
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    
    if violation_type == "tab_switch":
        attempt.tab_switches += 1
        if attempt.tab_switches >= 3:
            attempt.is_flagged = True
            attempt.flag_reason = f"Multiple tab switches: {attempt.tab_switches}"
    elif violation_type == "fullscreen_exit":
        attempt.fullscreen_exits += 1
        if attempt.fullscreen_exits >= 2:
            attempt.is_flagged = True
            attempt.flag_reason = f"Multiple fullscreen exits: {attempt.fullscreen_exits}"
    
    await db.commit()
    
    return {
        "tab_switches": attempt.tab_switches,
        "fullscreen_exits": attempt.fullscreen_exits,
        "is_flagged": attempt.is_flagged
    }


@router.get("/my-attempts", response_model=List[TestAttemptResponse])
async def get_my_attempts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current user's test attempts"""
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.user_id == current_user.id)
        .order_by(TestAttempt.started_at.desc())
    )
    attempts = result.scalars().all()
    
    responses = []
    for attempt in attempts:
        test_result = await db.execute(
            select(Test.title).where(Test.id == attempt.test_id)
        )
        test_title = test_result.scalar()
        
        responses.append(TestAttemptResponse(
            id=attempt.id,
            test_id=attempt.test_id,
            test_title=test_title,
            status=attempt.status,
            current_question=attempt.current_question,
            score=attempt.score,
            total_marks=attempt.total_marks,
            percentage=attempt.percentage,
            passed=attempt.passed,
            tab_switches=attempt.tab_switches,
            is_flagged=attempt.is_flagged,
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
            time_taken_seconds=attempt.time_taken_seconds
        ))
    
    return responses


@router.get("/result/{attempt_id}", response_model=TestResultResponse)
async def get_test_result(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed result for a completed test"""
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == current_user.id)
        .where(TestAttempt.status == "completed")
    )
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        raise HTTPException(status_code=404, detail="Test result not found")
    
    # Get test
    test_result = await db.execute(
        select(Test).where(Test.id == attempt.test_id)
    )
    test = test_result.scalar_one_or_none()
    
    # Get answers with questions
    answers_result = await db.execute(
        select(UserAnswer).where(UserAnswer.attempt_id == attempt_id)
    )
    answers = answers_result.scalars().all()
    
    answer_details = []
    for answer in answers:
        q_result = await db.execute(
            select(Question).where(Question.id == answer.question_id)
        )
        question = q_result.scalar_one_or_none()
        
        answer_details.append({
            "question_id": answer.question_id,
            "question_text": question.question_text if question else "",
            "user_answer": answer.answer_text,
            "correct_answer": question.correct_answer if question else None,
            "is_correct": answer.is_correct,
            "marks_obtained": answer.marks_obtained,
            "max_marks": question.marks if question else 0
        })
    
    return TestResultResponse(
        attempt_id=attempt.id,
        test_id=attempt.test_id,
        test_title=test.title if test else "Unknown",
        score=attempt.score,
        total_marks=attempt.total_marks,
        percentage=attempt.percentage,
        passed=attempt.passed,
        time_taken_seconds=attempt.time_taken_seconds or 0,
        completed_at=attempt.completed_at,
        answers=answer_details
    )


@router.get("/content-proxy")
async def proxy_content(
    url: str
):
    """
    Proxy endpoint to serve content with correct content-type/disposition.
    Uses streaming to prevent memory exhaustion (OOM) on large files.
    """
    import httpx
    from fastapi.responses import StreamingResponse
    from fastapi import HTTPException
    
    # Validate URL is from Cloudinary, Supabase, or our backend
    allowed_domains = [
        "https://res.cloudinary.com/",
        "https://rmysstjbjaaqctbbswmj.supabase.co/",
        "/"
    ]
    if not any(url.startswith(domain) for domain in allowed_domains):
        raise HTTPException(status_code=400, detail="Invalid URL source")
    
    try:
        # We use a generator to keep the client session open during streaming
        async def stream_generator():
            async with httpx.AsyncClient() as client:
                try:
                    async with client.stream("GET", url, timeout=60.0) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes():
                            yield chunk
                except httpx.HTTPError as e:
                    # Log error or handle gracefully (streaming might have started)
                    print(f"Stream error: {e}")
                    raise

        # Fetch header info first to set media_type correctly without loading body
        async with httpx.AsyncClient() as client:
             head_response = await client.head(url, timeout=10.0)
        
        # Default to upstream content-type
        media_type = head_response.headers.get("content-type", "application/octet-stream")
        
        # FORCE override based on file extension because Supabase/upstream often sends text/plain
        lower_url = url.lower()
        if lower_url.endswith('.html') or lower_url.endswith('.htm'):
            media_type = "text/html; charset=utf-8"
        elif lower_url.endswith('.pdf'):
            media_type = "application/pdf"
            
        # Override header for PDF/HTML inline display if needed
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Content-Disposition": "inline"
        }

        return StreamingResponse(
            stream_generator(),
            media_type=media_type,
            headers=headers
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch content: {str(e)}")

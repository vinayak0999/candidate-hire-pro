"""
Test Engine API endpoints for candidates to take tests

RELIABILITY FEATURES:
- All submission endpoints have retry logic
- Emergency submit endpoint for when normal submit fails
- Heartbeat endpoint for connection monitoring
- Auto-save for crash recovery
- Idempotent completion (safe to call multiple times)
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime, timezone
import asyncio

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


# ============================================================================
# RELIABILITY ENDPOINTS - Call these to ensure test submission never fails
# ============================================================================

@router.get("/heartbeat/{attempt_id}")
async def test_heartbeat(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Heartbeat endpoint - frontend should call every 30 seconds.

    Returns:
    - Connection status (if this works, backend is reachable)
    - Remaining time
    - Whether answers are being saved

    Frontend should show warning if this fails 3 times in a row.
    """
    try:
        result = await db.execute(
            select(TestAttempt)
            .where(TestAttempt.id == attempt_id)
            .where(TestAttempt.user_id == current_user.id)
        )
        attempt = result.scalar_one_or_none()

        if not attempt:
            return {"status": "error", "message": "Attempt not found"}

        # Get test for duration
        test_result = await db.execute(
            select(Test).where(Test.id == attempt.test_id)
        )
        test = test_result.scalar_one_or_none()

        # Calculate remaining time
        remaining_seconds = None
        if attempt.started_at and test:
            started_at = attempt.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            remaining_seconds = max(0, (test.duration_minutes * 60) - elapsed)

        # Count saved answers
        answer_count = await db.execute(
            select(func.count(UserAnswer.id))
            .where(UserAnswer.attempt_id == attempt_id)
        )
        saved_answers = answer_count.scalar() or 0

        return {
            "status": "ok",
            "attempt_status": attempt.status,
            "remaining_seconds": remaining_seconds,
            "saved_answers": saved_answers,
            "server_time": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


# ============================================================================
# HEARTBEAT - Keep session alive during long tests
# ============================================================================

@router.post("/heartbeat/{attempt_id}")
async def heartbeat(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Keep test session alive during long tests (1.5+ hours).
    
    Called every 2 minutes by frontend to:
    - Prevent connection timeouts
    - Update last activity timestamp
    - Verify session is still valid
    """
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == current_user.id)
        .where(TestAttempt.status == "in_progress")
    )
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        return {"alive": False, "reason": "attempt_not_found_or_completed"}
    
    # Update last_activity timestamp if the field exists
    # This helps track active sessions
    try:
        if hasattr(attempt, 'last_activity'):
            attempt.last_activity = datetime.now(timezone.utc)
            await db.commit()
    except:
        pass  # Field might not exist, that's ok
    
    return {
        "alive": True,
        "attempt_id": attempt_id,
        "status": attempt.status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.post("/emergency-submit/{attempt_id}")
async def emergency_submit_test(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    EMERGENCY SUBMIT - Use when normal /complete fails.

    This endpoint:
    - Has maximum retry attempts (5)
    - Uses longer timeouts
    - Skips non-essential operations
    - Will ALWAYS try to mark test as completed
    - Returns success even on partial failures

    Frontend should call this if /complete fails 2+ times.
    """
    max_retries = 5
    last_error = None

    for retry in range(max_retries):
        try:
            # Get attempt with minimal validation
            result = await db.execute(
                select(TestAttempt).where(TestAttempt.id == attempt_id)
            )
            attempt = result.scalar_one_or_none()

            if not attempt:
                return {"success": False, "error": "Attempt not found"}

            # Already completed? Return success
            if attempt.status == "completed":
                return {
                    "success": True,
                    "message": "Test already completed",
                    "score": attempt.score,
                    "percentage": attempt.percentage
                }

            # Get test info
            test_result = await db.execute(
                select(Test).where(Test.id == attempt.test_id)
            )
            test = test_result.scalar_one_or_none()

            # Calculate score from whatever answers we have
            answers_result = await db.execute(
                select(UserAnswer).where(UserAnswer.attempt_id == attempt_id)
            )
            answers = answers_result.scalars().all()

            total_score = sum(a.marks_obtained or 0 for a in answers)
            total_marks = attempt.total_marks or (test.total_marks if test else 100)
            percentage = (total_score / total_marks * 100) if total_marks > 0 else 0

            # Update attempt - MINIMAL operations only
            now = datetime.now(timezone.utc)
            attempt.status = "completed"
            attempt.score = total_score
            attempt.percentage = percentage
            attempt.passed = percentage >= 50
            attempt.completed_at = now

            if attempt.started_at:
                started_at = attempt.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                attempt.time_taken_seconds = int((now - started_at).total_seconds())

            await db.commit()

            print(f"✅ EMERGENCY SUBMIT SUCCESS: attempt {attempt_id}, score {total_score}/{total_marks}")

            return {
                "success": True,
                "message": "Test submitted successfully (emergency)",
                "attempt_id": attempt.id,
                "score": total_score,
                "total_marks": total_marks,
                "percentage": percentage,
                "passed": percentage >= 50,
                "answers_saved": len(answers)
            }

        except Exception as e:
            last_error = str(e)
            print(f"⚠️ Emergency submit attempt {retry + 1}/{max_retries} failed: {last_error}")

            try:
                await db.rollback()
            except:
                pass

            if retry < max_retries - 1:
                await asyncio.sleep(1 * (retry + 1))  # Longer backoff
                continue

    # All retries failed - this is VERY bad
    print(f"🔴 CRITICAL: Emergency submit FAILED for attempt {attempt_id}: {last_error}")

    return {
        "success": False,
        "error": f"Failed after {max_retries} attempts: {last_error}",
        "message": "Please contact support immediately with your attempt ID",
        "attempt_id": attempt_id
    }


@router.post("/emergency-submit-no-auth/{attempt_id}")
async def emergency_submit_no_auth(
    attempt_id: int,
    email: str,  # Verify by email instead of JWT
    db: AsyncSession = Depends(get_db)
):
    """
    LAST RESORT emergency submit - works even if JWT expired.

    Verifies user by email instead of token.
    Use this ONLY when all other methods fail.

    Frontend should call this if token is expired and normal submit fails.
    """
    from ..models.user import User

    # Find user by email
    user_result = await db.execute(
        select(User).where(User.email == email.lower().strip())
    )
    user = user_result.scalar_one_or_none()

    if not user:
        return {"success": False, "error": "User not found"}

    # Verify attempt belongs to this user
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == user.id)
    )
    attempt = result.scalar_one_or_none()

    if not attempt:
        return {"success": False, "error": "Attempt not found or doesn't belong to this user"}

    if attempt.status == "completed":
        return {
            "success": True,
            "message": "Test already completed",
            "score": attempt.score,
            "percentage": attempt.percentage
        }

    # Get test and calculate score
    test_result = await db.execute(
        select(Test).where(Test.id == attempt.test_id)
    )
    test = test_result.scalar_one_or_none()

    answers_result = await db.execute(
        select(UserAnswer).where(UserAnswer.attempt_id == attempt_id)
    )
    answers = answers_result.scalars().all()

    total_score = sum(a.marks_obtained or 0 for a in answers)
    total_marks = attempt.total_marks or (test.total_marks if test else 100)
    percentage = (total_score / total_marks * 100) if total_marks > 0 else 0

    # Complete the test
    now = datetime.now(timezone.utc)
    attempt.status = "completed"
    attempt.score = total_score
    attempt.percentage = percentage
    attempt.passed = percentage >= 50
    attempt.completed_at = now
    attempt.is_flagged = True
    attempt.flag_reason = (attempt.flag_reason or "") + " | Emergency no-auth submit"

    if attempt.started_at:
        started_at = attempt.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        attempt.time_taken_seconds = int((now - started_at).total_seconds())

    await db.commit()

    print(f"✅ EMERGENCY NO-AUTH SUBMIT: attempt {attempt_id}, user {email}, score {total_score}")

    return {
        "success": True,
        "message": "Test submitted via emergency no-auth",
        "attempt_id": attempt.id,
        "score": total_score,
        "total_marks": total_marks,
        "percentage": percentage,
        "passed": percentage >= 50
    }


@router.post("/bulk-save-answers/{attempt_id}")
async def bulk_save_answers(
    attempt_id: int,
    answers: List[SubmitAnswerRequest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Save ALL answers in a single transaction.

    Frontend should call this:
    - Before calling /complete
    - Periodically during test (every 2 minutes)
    - When user tries to close browser

    More reliable than saving answers one-by-one.
    """
    # Verify attempt
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == current_user.id)
    )
    attempt = result.scalar_one_or_none()

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    if attempt.status == "completed":
        return {"saved": 0, "message": "Test already completed"}

    saved_count = 0
    errors = []

    # Get all questions for scoring
    question_ids = [a.question_id for a in answers]
    if question_ids:
        q_result = await db.execute(
            select(Question).where(Question.id.in_(question_ids))
        )
        questions_map = {q.id: q for q in q_result.scalars().all()}
    else:
        questions_map = {}

    # Helper to normalize answer to option ID
    def normalize_to_option_id(options, text_or_id):
        """Convert text answer to option ID for consistent comparison"""
        if not options or not text_or_id:
            return text_or_id
        # First check if it's already an ID
        for opt in options:
            if isinstance(opt, dict) and opt.get('id') == text_or_id:
                return text_or_id  # Already an ID
        # Then check if it's text that matches an option
        for opt in options:
            if isinstance(opt, dict) and opt.get('text') == text_or_id:
                return opt.get('id', text_or_id)
        return text_or_id  # Return as-is if not found

    for answer_data in answers:
        try:
            question = questions_map.get(answer_data.question_id)

            # Normalize the answer for MCQ questions
            normalized_answer = answer_data.answer_text
            if question and question.question_type == "mcq" and question.options:
                normalized_answer = normalize_to_option_id(question.options, answer_data.answer_text)

            # Check existing
            existing_result = await db.execute(
                select(UserAnswer)
                .where(UserAnswer.attempt_id == attempt_id)
                .where(UserAnswer.question_id == answer_data.question_id)
            )
            existing = existing_result.scalar_one_or_none()

            # Calculate score for MCQ
            is_correct = None
            marks_obtained = 0
            if question and question.question_type == "mcq" and question.correct_answer:
                is_correct = (normalized_answer == question.correct_answer)
                marks_obtained = question.marks if is_correct else 0

            if existing:
                existing.answer_text = normalized_answer
                existing.annotation_data = answer_data.annotation_data
                existing.time_spent_seconds = answer_data.time_spent_seconds
                existing.answered_at = datetime.now(timezone.utc)
                existing.is_correct = is_correct
                existing.marks_obtained = marks_obtained
            else:
                new_answer = UserAnswer(
                    attempt_id=attempt_id,
                    question_id=answer_data.question_id,
                    answer_text=normalized_answer,
                    annotation_data=answer_data.annotation_data,
                    is_correct=is_correct,
                    marks_obtained=marks_obtained,
                    time_spent_seconds=answer_data.time_spent_seconds
                )
                db.add(new_answer)

            saved_count += 1

        except Exception as e:
            errors.append({"question_id": answer_data.question_id, "error": str(e)[:50]})

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save answers: {str(e)[:100]}")

    return {
        "saved": saved_count,
        "total": len(answers),
        "errors": errors if errors else None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ============================================================================
# STANDARD ENDPOINTS
# ============================================================================


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
    
    # CRITICAL: Prevent starting test with no questions
    if not questions:
        # Delete the attempt we just created since test can't proceed
        if not existing_attempt:
            await db.delete(attempt)
            await db.commit()
        raise HTTPException(
            status_code=400,
            detail="This test has no questions configured. Please contact the administrator."
        )
    
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
    
    # If still no questions, return None (cannot resume without questions)
    if not questions:
        return None
    
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
    """
    Submit an answer for a question.

    Robust implementation:
    - Single transaction (no partial saves)
    - Retry on transient failures
    - Proper error handling
    """
    import asyncio

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

    # Retry logic for transient DB failures
    max_retries = 3
    last_error = None

    for attempt_num in range(max_retries):
        try:
            # Check if answer already exists
            existing_result = await db.execute(
                select(UserAnswer)
                .where(UserAnswer.attempt_id == attempt_id)
                .where(UserAnswer.question_id == data.question_id)
            )
            existing_answer = existing_result.scalar_one_or_none()

            # Helper to normalize answer to option ID
            def normalize_to_option_id(options, text_or_id):
                """Convert text answer to option ID for consistent comparison"""
                if not options or not text_or_id:
                    return text_or_id
                # First check if it's already an ID
                for opt in options:
                    if isinstance(opt, dict) and opt.get('id') == text_or_id:
                        return text_or_id  # Already an ID
                # Then check if it's text that matches an option
                for opt in options:
                    if isinstance(opt, dict) and opt.get('text') == text_or_id:
                        return opt.get('id', text_or_id)
                return text_or_id  # Return as-is if not found

            # Normalize the answer for MCQ questions
            normalized_answer = data.answer_text
            if question.question_type == "mcq" and question.options:
                normalized_answer = normalize_to_option_id(question.options, data.answer_text)

            if existing_answer:
                # Update existing answer
                existing_answer.answer_text = normalized_answer
                existing_answer.annotation_data = data.annotation_data
                existing_answer.time_spent_seconds = data.time_spent_seconds
                existing_answer.answered_at = datetime.now(timezone.utc)

                # Auto-score for MCQ
                if question.question_type == "mcq" and question.correct_answer:
                    existing_answer.is_correct = (normalized_answer == question.correct_answer)
                    existing_answer.marks_obtained = question.marks if existing_answer.is_correct else 0

                await db.commit()
                return {"message": "Answer updated", "answer_id": existing_answer.id, "saved": True}
            else:
                # Create new answer
                is_correct = None
                marks_obtained = 0

                # Auto-score for MCQ
                if question.question_type == "mcq" and question.correct_answer:
                    is_correct = (normalized_answer == question.correct_answer)
                    marks_obtained = question.marks if is_correct else 0

                answer = UserAnswer(
                    attempt_id=attempt_id,
                    question_id=data.question_id,
                    answer_text=normalized_answer,  # Store normalized ID
                    annotation_data=data.annotation_data,
                    is_correct=is_correct,
                    marks_obtained=marks_obtained,
                    time_spent_seconds=data.time_spent_seconds
                )
                db.add(answer)

                # Update current question in attempt - SINGLE transaction
                attempt.current_question += 1

                await db.commit()
                await db.refresh(answer)

                return {"message": "Answer submitted", "answer_id": answer.id, "saved": True}

        except Exception as e:
            last_error = str(e)
            print(f"Answer submit attempt {attempt_num + 1}/{max_retries} failed: {last_error}")
            await db.rollback()

            if attempt_num < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt_num + 1))  # Backoff
                continue

    # All retries failed
    raise HTTPException(
        status_code=500,
        detail=f"Failed to save answer after {max_retries} attempts. Please try again."
    )


@router.post("/auto-save-answer")
async def auto_save_answer(
    attempt_id: int,
    data: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Auto-save answer as draft (called periodically by frontend).

    Lighter than submit-answer:
    - No validation errors shown to user
    - Silent failure (returns success even if save fails)
    - Used for crash recovery
    """
    try:
        # Verify attempt
        result = await db.execute(
            select(TestAttempt)
            .where(TestAttempt.id == attempt_id)
            .where(TestAttempt.user_id == current_user.id)
            .where(TestAttempt.status == "in_progress")
        )
        attempt = result.scalar_one_or_none()

        if not attempt:
            return {"saved": False, "reason": "attempt_not_found"}

        # Upsert answer
        existing_result = await db.execute(
            select(UserAnswer)
            .where(UserAnswer.attempt_id == attempt_id)
            .where(UserAnswer.question_id == data.question_id)
        )
        existing_answer = existing_result.scalar_one_or_none()

        if existing_answer:
            existing_answer.answer_text = data.answer_text
            existing_answer.annotation_data = data.annotation_data
            existing_answer.time_spent_seconds = data.time_spent_seconds
            existing_answer.answered_at = datetime.now(timezone.utc)
        else:
            answer = UserAnswer(
                attempt_id=attempt_id,
                question_id=data.question_id,
                answer_text=data.answer_text,
                annotation_data=data.annotation_data,
                time_spent_seconds=data.time_spent_seconds
            )
            db.add(answer)

        await db.commit()
        return {"saved": True, "timestamp": datetime.now(timezone.utc).isoformat()}

    except Exception as e:
        print(f"Auto-save failed (non-critical): {e}")
        try:
            await db.rollback()
        except:
            pass
        return {"saved": False, "reason": "db_error"}


@router.post("/upload-answer-file")
async def upload_answer_file(
    file: UploadFile = File(...),
    attempt_id: int = Form(...),
    question_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload Excel/CSV file as answer for agent_analysis questions.

    Robust implementation:
    - Retries Supabase upload 3 times
    - Falls back to local storage if Supabase fails
    - Ensures file is NEVER lost
    """
    import os
    import aiofiles
    import asyncio
    from datetime import datetime

    # Verify attempt belongs to user
    attempt_result = await db.execute(
        select(TestAttempt).where(
            TestAttempt.id == attempt_id,
            TestAttempt.user_id == current_user.id
        )
    )
    attempt = attempt_result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    # Validate file type
    allowed_extensions = {'.xlsx', '.xls', '.csv'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Only Excel (.xlsx, .xls) and CSV files allowed")

    # Read file content FIRST (ensures we have the data before any upload attempt)
    file_content = await file.read()

    # Build file path
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{attempt_id}_{question_id}_{timestamp}{ext}"
    safe_filename = filename.replace(" ", "_")
    file_path = f"answers/{safe_filename}"

    public_url = None

    # BEST PRACTICE: Primary = Supabase, Fallback = AWS S3
    # Both are cloud storage, ensuring production compatibility
    
    # 1. Try Supabase (primary)
    try:
        from ..services.supabase_upload import upload_bytes_to_supabase

        for attempt_num in range(3):
            try:
                public_url = await upload_bytes_to_supabase(
                    content=file_content,
                    bucket="division-docs",
                    file_path=file_path,
                    content_type=file.content_type or "application/octet-stream"
                )
                print(f"✅ Answer file uploaded to Supabase: {public_url}")
                break
            except Exception as e:
                print(f"Supabase upload attempt {attempt_num + 1}/3 failed: {e}")
                if attempt_num < 2:
                    await asyncio.sleep(1 * (attempt_num + 1))
    except Exception as e:
        print(f"Supabase module error: {e}")

    # 2. Fallback to AWS S3 (cloud-based, production-safe)
    if not public_url:
        print("⚠️ Supabase failed, trying AWS S3 fallback...")
        try:
            import boto3
            from botocore.config import Config
            
            s3 = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'ap-south-1'),
                config=Config(signature_version='s3v4')
            )
            
            s3_bucket = 'autonex-hire'
            s3_key = f"answer-files/{safe_filename}"
            
            # Upload to S3
            s3.put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=file_content,
                ContentType=file.content_type or "application/octet-stream"
            )
            
            public_url = f"https://{s3_bucket}.s3.ap-south-1.amazonaws.com/{s3_key}"
            print(f"✅ Answer file uploaded to S3 fallback: {public_url}")
        except Exception as e:
            print(f"S3 fallback also failed: {e}")

    # 3. If both cloud options failed, return user-friendly error
    if not public_url:
        raise HTTPException(
            status_code=503,
            detail="Cloud storage temporarily unavailable. Please try again in a few moments."
        )
    
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
    """
    Complete a test and get results.

    Robust implementation:
    - Retry on transient failures
    - Ensures test completion is NEVER lost
    - Returns cached result if already completed (idempotent)
    """
    import asyncio

    # Verify attempt belongs to user
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == current_user.id)
    )
    attempt = result.scalar_one_or_none()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")

    # Helper to get option text from ID
    def get_option_text(options, option_id):
        """Get the text of an option by its ID"""
        if not options or not option_id:
            return option_id
        for opt in options:
            if isinstance(opt, dict) and opt.get('id') == option_id:
                return opt.get('text', option_id)
        return option_id  # Return ID if not found

    # If already completed, return the existing result (idempotent)
    if attempt.status == "completed":
        # Fetch and return existing results
        test_result = await db.execute(
            select(Test).where(Test.id == attempt.test_id)
        )
        test = test_result.scalar_one_or_none()

        answers_result = await db.execute(
            select(UserAnswer).where(UserAnswer.attempt_id == attempt_id)
        )
        answers = answers_result.scalars().all()

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
            # Convert IDs to text for display
            user_answer_text = get_option_text(question.options, answer.answer_text) if question else answer.answer_text
            correct_answer_text = get_option_text(question.options, question.correct_answer) if question else None
            answer_details.append({
                "question_id": answer.question_id,
                "question_text": question.question_text if question else "",
                "user_answer": user_answer_text,
                "correct_answer": correct_answer_text,
                "is_correct": answer.is_correct,
                "marks_obtained": answer.marks_obtained,
                "max_marks": question.marks if question else 0
            })

        return TestResultResponse(
            attempt_id=attempt.id,
            test_id=attempt.test_id,
            test_title=test.title if test else "Unknown",
            score=attempt.score or 0,
            total_marks=attempt.total_marks or (test.total_marks if test else 0),
            percentage=attempt.percentage or 0,
            passed=attempt.passed or False,
            time_taken_seconds=attempt.time_taken_seconds or 0,
            completed_at=attempt.completed_at,
            answers=answer_details
        )

    # Retry logic for completion
    max_retries = 3
    last_error = None

    for retry in range(max_retries):
        try:
            # Update tab switches if provided
            if data and data.tab_switches:
                attempt.tab_switches = max(attempt.tab_switches or 0, data.tab_switches)
                if attempt.tab_switches >= 3:
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

            total_score = sum(a.marks_obtained or 0 for a in answers)
            total_marks = attempt.total_marks or (test.total_marks if test else 0)
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
            if started_at and started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            if started_at:
                attempt.time_taken_seconds = int((now - started_at).total_seconds())

            await db.commit()
            await db.refresh(attempt)
            break  # Success!

        except Exception as e:
            last_error = str(e)
            print(f"Test completion attempt {retry + 1}/{max_retries} failed: {last_error}")
            await db.rollback()

            if retry < max_retries - 1:
                await asyncio.sleep(0.5 * (retry + 1))
                # Re-fetch attempt for next retry
                result = await db.execute(
                    select(TestAttempt)
                    .where(TestAttempt.id == attempt_id)
                    .where(TestAttempt.user_id == current_user.id)
                )
                attempt = result.scalar_one_or_none()
                if not attempt:
                    raise HTTPException(status_code=404, detail="Test attempt not found")
                continue

            raise HTTPException(
                status_code=500,
                detail=f"Failed to complete test after {max_retries} attempts. Your answers are saved - please try again."
            )
    
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
        # Convert IDs to text for display
        user_answer_text = get_option_text(question.options, answer.answer_text) if question else answer.answer_text
        correct_answer_text = get_option_text(question.options, question.correct_answer) if question else None
        answer_details.append({
            "question_id": answer.question_id,
            "question_text": question.question_text if question else "",
            "user_answer": user_answer_text,
            "correct_answer": correct_answer_text,
            "is_correct": answer.is_correct,
            "marks_obtained": answer.marks_obtained,
            "max_marks": question.marks if question else 0
        })
    
    return TestResultResponse(
        attempt_id=attempt.id,
        test_id=attempt.test_id,
        test_title=test.title if test else "Unknown",
        score=attempt.score or 0,
        total_marks=total_marks or 0,
        percentage=attempt.percentage or 0,
        passed=attempt.passed or False,
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


@router.get("/recover-answers/{attempt_id}")
async def recover_saved_answers(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recover all saved answers for an attempt (for frontend crash recovery).

    Use this when:
    - Browser crashed during test
    - User accidentally closed tab
    - Network disconnection during test

    Returns all saved answers so frontend can restore state.
    """
    # Verify attempt belongs to user
    result = await db.execute(
        select(TestAttempt)
        .where(TestAttempt.id == attempt_id)
        .where(TestAttempt.user_id == current_user.id)
    )
    attempt = result.scalar_one_or_none()

    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")

    # Get all saved answers
    answers_result = await db.execute(
        select(UserAnswer).where(UserAnswer.attempt_id == attempt_id)
    )
    answers = answers_result.scalars().all()

    # Get test info
    test_result = await db.execute(
        select(Test).where(Test.id == attempt.test_id)
    )
    test = test_result.scalar_one_or_none()

    # Calculate remaining time
    remaining_seconds = None
    if attempt.status == "in_progress" and attempt.started_at and test:
        started_at = attempt.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        total_seconds = test.duration_minutes * 60
        remaining_seconds = max(0, total_seconds - elapsed)

    return {
        "attempt_id": attempt.id,
        "test_id": attempt.test_id,
        "status": attempt.status,
        "current_question": attempt.current_question,
        "remaining_seconds": remaining_seconds,
        "is_expired": remaining_seconds is not None and remaining_seconds <= 0,
        "answers": [
            {
                "question_id": a.question_id,
                "answer_text": a.answer_text,
                "annotation_data": a.annotation_data,
                "time_spent_seconds": a.time_spent_seconds
            }
            for a in answers
        ]
    }


@router.post("/auto-complete-expired/{attempt_id}")
async def auto_complete_expired_test(
    attempt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Auto-complete an expired test attempt.

    Called when:
    - Test timer runs out
    - User returns to expired test
    - Frontend detects time exceeded

    Saves all answers and marks test as completed with current score.
    """
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
        return {"message": "Test already completed", "attempt_id": attempt.id}

    # Get test to verify expiration
    test_result = await db.execute(
        select(Test).where(Test.id == attempt.test_id)
    )
    test = test_result.scalar_one_or_none()

    # Check if actually expired (allow 1 minute grace period)
    if attempt.started_at and test:
        started_at = attempt.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        total_seconds = (test.duration_minutes * 60) + 60  # 1 min grace

        if elapsed < total_seconds:
            raise HTTPException(
                status_code=400,
                detail="Test has not expired yet. Use /complete endpoint instead."
            )

    # Calculate score from saved answers
    answers_result = await db.execute(
        select(UserAnswer).where(UserAnswer.attempt_id == attempt_id)
    )
    answers = answers_result.scalars().all()

    total_score = sum(a.marks_obtained or 0 for a in answers)
    total_marks = attempt.total_marks or (test.total_marks if test else 0)
    percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
    passed = percentage >= 50

    # Mark as completed
    now = datetime.now(timezone.utc)
    attempt.status = "completed"
    attempt.score = total_score
    attempt.percentage = percentage
    attempt.passed = passed
    attempt.completed_at = now
    attempt.is_flagged = True
    attempt.flag_reason = (attempt.flag_reason or "") + " | Auto-completed (time expired)"

    if attempt.started_at:
        started_at = attempt.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        attempt.time_taken_seconds = int((now - started_at).total_seconds())

    await db.commit()

    return {
        "message": "Test auto-completed due to time expiration",
        "attempt_id": attempt.id,
        "score": total_score,
        "percentage": percentage,
        "passed": passed
    }


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
    
    # Helper to get option text from ID
    def get_option_text(options, option_id):
        """Get the text of an option by its ID"""
        if not options or not option_id:
            return option_id
        for opt in options:
            if isinstance(opt, dict) and opt.get('id') == option_id:
                return opt.get('text', option_id)
        return option_id  # Return ID if not found

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

        # Convert IDs to text for display
        user_answer_text = get_option_text(question.options, answer.answer_text) if question else answer.answer_text
        correct_answer_text = get_option_text(question.options, question.correct_answer) if question else None

        answer_details.append({
            "question_id": answer.question_id,
            "question_text": question.question_text if question else "",
            "user_answer": user_answer_text,
            "correct_answer": correct_answer_text,
            "is_correct": answer.is_correct,
            "marks_obtained": answer.marks_obtained,
            "max_marks": question.marks if question else 0
        })

    return TestResultResponse(
        attempt_id=attempt.id,
        test_id=attempt.test_id,
        test_title=test.title if test else "Unknown",
        score=attempt.score or 0,
        total_marks=attempt.total_marks or 0,
        percentage=attempt.percentage or 0,
        passed=attempt.passed or False,
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
    Optimized for 10k+ concurrent users.
    """
    import httpx
    from fastapi.responses import StreamingResponse, RedirectResponse
    from fastapi import HTTPException

    # Validate URL is from Cloudinary, Supabase, or our backend
    allowed_domains = [
        "https://res.cloudinary.com/",
        "https://rmysstjbjaaqctbbswmj.supabase.co/",
        "/"
    ]
    if not any(url.startswith(domain) for domain in allowed_domains):
        raise HTTPException(status_code=400, detail="Invalid URL source")

    # For Supabase public files, redirect directly to avoid proxying
    # This is much more efficient for large files (12MB HTML, etc.)
    if url.startswith("https://rmysstjbjaaqctbbswmj.supabase.co/storage/v1/object/public/"):
        # Return redirect for browsers to fetch directly from CDN
        # This dramatically reduces server memory usage
        return RedirectResponse(url=url, status_code=302)

    try:
        # For non-public URLs, stream with optimizations
        async def stream_generator():
            # Use connection pooling with limits
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            async with httpx.AsyncClient(limits=limits, timeout=30.0) as client:
                try:
                    # Smaller chunk size (32KB) to reduce memory per connection
                    async with client.stream("GET", url, timeout=60.0) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes(chunk_size=32768):
                            yield chunk
                except httpx.HTTPError as e:
                    print(f"Stream error: {e}")
                    raise

        # Fetch header info first to set media_type correctly without loading body
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            head_response = await client.head(url, timeout=10.0)

        # Default to upstream content-type
        media_type = head_response.headers.get("content-type", "application/octet-stream")
        content_length = head_response.headers.get("content-length")

        # FORCE override based on file extension because Supabase/upstream often sends text/plain
        lower_url = url.lower()
        if lower_url.endswith('.html') or lower_url.endswith('.htm'):
            media_type = "text/html; charset=utf-8"
        elif lower_url.endswith('.pdf'):
            media_type = "application/pdf"

        # Headers for inline display and caching
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Content-Disposition": "inline",
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
        }
        if content_length:
            headers["Content-Length"] = content_length

        return StreamingResponse(
            stream_generator(),
            media_type=media_type,
            headers=headers
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch content: {str(e)}")

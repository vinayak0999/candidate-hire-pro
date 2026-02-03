"""
Script to re-evaluate all completed test attempts and fix incorrect scores.
This fixes the bug where answers were compared as text vs ID.

Run with: python3 fix_evaluation_results.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload
from app.database import async_session_maker, init_db
from app.models.test import Test, TestSection, Question, TestAttempt, UserAnswer


def get_option_id(options, text_or_id):
    """Convert text answer to option ID for consistent comparison"""
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


async def fix_all_results():
    """Re-evaluate all completed attempts and fix scores."""
    await init_db()

    async with async_session_maker() as db:
        print("=" * 60)
        print("FIXING ALL TEST EVALUATION RESULTS")
        print("=" * 60)

        # Get all completed attempts
        result = await db.execute(
            select(TestAttempt)
            .options(selectinload(TestAttempt.answers))
            .where(TestAttempt.status == "completed")
            .order_by(TestAttempt.id)
        )
        attempts = result.scalars().all()

        print(f"\nFound {len(attempts)} completed attempts to fix.\n")

        fixed_count = 0
        error_count = 0

        for attempt in attempts:
            try:
                # Get the test with sections and questions
                test_result = await db.execute(
                    select(Test)
                    .options(
                        selectinload(Test.sections).selectinload(TestSection.questions)
                    )
                    .where(Test.id == attempt.test_id)
                )
                test = test_result.scalar_one_or_none()

                if not test:
                    print(f"  ⚠️  Attempt {attempt.id}: Test {attempt.test_id} not found, skipping")
                    continue

                # Build question lookup from sections
                question_lookup = {}
                if test.sections:
                    for section in test.sections:
                        if section.questions:
                            for q in section.questions:
                                question_lookup[q.id] = q

                if not question_lookup:
                    print(f"  ⚠️  Attempt {attempt.id}: No questions found for test {attempt.test_id}, skipping")
                    continue

                # Get answers (already loaded via selectinload)
                answers = attempt.answers

                if not answers:
                    print(f"  ⚠️  Attempt {attempt.id}: No answers found, skipping")
                    continue

                # Re-evaluate each answer
                total_score = 0.0
                correct_count = 0
                total_questions = len(answers)
                old_score = attempt.score or 0

                for answer in answers:
                    question = question_lookup.get(answer.question_id)
                    if not question:
                        continue

                    # Normalize the user's answer
                    user_answer_normalized = get_option_id(question.options, answer.answer_text)

                    # Compare with correct answer
                    correct_answer = question.correct_answer or ""
                    is_correct = (user_answer_normalized == correct_answer)
                    marks = float(question.marks) if is_correct else 0.0

                    # Update the answer record
                    answer.answer_text = user_answer_normalized  # Store normalized ID
                    answer.is_correct = is_correct
                    answer.marks_obtained = marks

                    total_score += marks
                    if is_correct:
                        correct_count += 1

                # Update attempt totals
                total_marks = attempt.total_marks or test.total_marks or 100
                percentage = (total_score / total_marks * 100) if total_marks > 0 else 0

                # Use test passing marks or default to 50%
                passing_marks = test.passing_marks if test.passing_marks else (total_marks * 0.5)
                passed = total_score >= passing_marks

                attempt.score = total_score
                attempt.percentage = percentage
                attempt.passed = passed

                # Commit changes for this attempt
                await db.commit()

                # Print result
                score_change = total_score - old_score
                status = "✅" if score_change > 0 else ("➡️ " if score_change == 0 else "⬇️")
                print(f"  {status} Attempt {attempt.id} (User {attempt.user_id}): {old_score} → {total_score}/{total_marks} ({correct_count}/{total_questions} correct) [{'+' if score_change >= 0 else ''}{score_change:.1f}]")

                fixed_count += 1

            except Exception as e:
                import traceback
                print(f"  ❌ Attempt {attempt.id}: Error - {str(e)[:100]}")
                traceback.print_exc()
                error_count += 1
                await db.rollback()

        print("\n" + "=" * 60)
        print(f"COMPLETE: Fixed {fixed_count} attempts, {error_count} errors")
        print("=" * 60)


if __name__ == "__main__":
    print("\n🔧 Starting evaluation fix script...\n")
    asyncio.run(fix_all_results())
    print("\n✅ Done!\n")

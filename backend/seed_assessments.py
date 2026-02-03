"""
Seed script to create sample English and Logical Reasoning assessments
with all questions and correct answers for auto-evaluation.

Run with: python3 seed_assessments.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import async_session_maker, init_db
from app.models.test import Test, TestSection, Question


async def seed_assessments():
    """Create English and Logical Reasoning assessments with full question sets."""
    await init_db()
    
    async with async_session_maker() as db:
        print("🚀 Creating sample assessments...")
        
        # ========== ENGLISH PROFICIENCY TEST ==========
        english_test = Test(
            title="English Proficiency Test",
            description="Comprehensive English test covering grammar, vocabulary, and reading comprehension.",
            category="English",
            assessment_type="standalone_assessment",
            duration_minutes=60,
            passing_marks=15,  # 60% of 25
            total_questions=20,
            total_marks=25,
            is_published=True,
            is_active=True,
            enable_tab_switch_detection=True,
            max_tab_switches_allowed=3
        )
        db.add(english_test)
        await db.flush()
        
        # Section A: Grammar & Vocabulary
        section_a = TestSection(
            test_id=english_test.id,
            title="Section A: Grammar & Vocabulary",
            instructions="Choose the correct option to complete each sentence. (15 marks, 1 mark each)",
            total_marks=15,
            order=1
        )
        db.add(section_a)
        await db.flush()
        
        # Grammar questions - Part 1: Complete sentences
        grammar_questions_1 = [
            {
                "question_number": "1a",
                "question_text": "The project ________ by next Friday.",
                "options": [
                    {"id": "i", "text": "will complete"},
                    {"id": "ii", "text": "will be completed"},
                    {"id": "iii", "text": "completes"},
                    {"id": "iv", "text": "completing"}
                ],
                "correct_answer": "ii",
                "marks": 1
            },
            {
                "question_number": "1b",
                "question_text": "Neither the manager nor the employees ________ present at the meeting.",
                "options": [
                    {"id": "i", "text": "was"},
                    {"id": "ii", "text": "were"},
                    {"id": "iii", "text": "is"},
                    {"id": "iv", "text": "are"}
                ],
                "correct_answer": "ii",
                "marks": 1
            },
            {
                "question_number": "1c",
                "question_text": "She has been working here ________ five years.",
                "options": [
                    {"id": "i", "text": "since"},
                    {"id": "ii", "text": "for"},
                    {"id": "iii", "text": "from"},
                    {"id": "iv", "text": "during"}
                ],
                "correct_answer": "ii",
                "marks": 1
            },
            {
                "question_number": "1d",
                "question_text": "The report needs to be submitted ________ you leave today.",
                "options": [
                    {"id": "i", "text": "before"},
                    {"id": "ii", "text": "until"},
                    {"id": "iii", "text": "unless"},
                    {"id": "iv", "text": "while"}
                ],
                "correct_answer": "i",
                "marks": 1
            },
            {
                "question_number": "1e",
                "question_text": "This is the most ________ solution we've found so far.",
                "options": [
                    {"id": "i", "text": "effective"},
                    {"id": "ii", "text": "more effective"},
                    {"id": "iii", "text": "effectiveness"},
                    {"id": "iv", "text": "effectively"}
                ],
                "correct_answer": "i",
                "marks": 1
            }
        ]
        
        # Grammar questions - Part 2: Error identification
        grammar_questions_2 = [
            {
                "question_number": "2a",
                "question_text": "Identify the error: 'The team have completed their assignment yesterday.'",
                "options": [
                    {"id": "i", "text": "have → had"},
                    {"id": "ii", "text": "completed → completing"},
                    {"id": "iii", "text": "their → its"},
                    {"id": "iv", "text": "No error"}
                ],
                "correct_answer": "i",
                "marks": 1
            },
            {
                "question_number": "2b",
                "question_text": "Identify the error: 'She don't have any experience in this field.'",
                "options": [
                    {"id": "i", "text": "don't → doesn't"},
                    {"id": "ii", "text": "have → has"},
                    {"id": "iii", "text": "any → some"},
                    {"id": "iv", "text": "No error"}
                ],
                "correct_answer": "i",
                "marks": 1
            },
            {
                "question_number": "2c",
                "question_text": "Identify the error: 'Please send the documents to John and myself.'",
                "options": [
                    {"id": "i", "text": "send → sent"},
                    {"id": "ii", "text": "to → for"},
                    {"id": "iii", "text": "myself → me"},
                    {"id": "iv", "text": "No error"}
                ],
                "correct_answer": "iii",
                "marks": 1
            },
            {
                "question_number": "2d",
                "question_text": "Identify the error: 'The company is looking for someone which can speak three languages.'",
                "options": [
                    {"id": "i", "text": "is → are"},
                    {"id": "ii", "text": "which → who"},
                    {"id": "iii", "text": "can → could"},
                    {"id": "iv", "text": "No error"}
                ],
                "correct_answer": "ii",
                "marks": 1
            },
            {
                "question_number": "2e",
                "question_text": "Identify the error: 'He is one of the employee who always meet deadlines.'",
                "options": [
                    {"id": "i", "text": "is → are"},
                    {"id": "ii", "text": "employee → employees"},
                    {"id": "iii", "text": "meet → meets"},
                    {"id": "iv", "text": "No error"}
                ],
                "correct_answer": "ii",
                "marks": 1
            }
        ]
        
        # Grammar questions - Part 3: Correct sentence
        grammar_questions_3 = [
            {
                "question_number": "3a",
                "question_text": "Choose the grammatically correct sentence:",
                "options": [
                    {"id": "i", "text": "Looking forward to hear from you soon."},
                    {"id": "ii", "text": "I look forward to hearing from you soon."},
                    {"id": "iii", "text": "I am looking forward to hear from you soon."},
                    {"id": "iv", "text": "Looking forward for hearing from you soon."}
                ],
                "correct_answer": "ii",
                "marks": 1
            },
            {
                "question_number": "3b",
                "question_text": "Choose the grammatically correct sentence:",
                "options": [
                    {"id": "i", "text": "Kindly do the needful at the earliest."},
                    {"id": "ii", "text": "Please take necessary action as soon as possible."},
                    {"id": "iii", "text": "Do what is needed urgently."},
                    {"id": "iv", "text": "Please be doing the necessary."}
                ],
                "correct_answer": "ii",
                "marks": 1
            },
            {
                "question_number": "3c",
                "question_text": "Choose the grammatically correct sentence:",
                "options": [
                    {"id": "i", "text": "The meeting will be held at 10 AM in the morning."},
                    {"id": "ii", "text": "The meeting will be held at 10 o'clock AM."},
                    {"id": "iii", "text": "The meeting will be held at 10 AM."},
                    {"id": "iv", "text": "The meeting will be held at 10 in the morning AM."}
                ],
                "correct_answer": "iii",
                "marks": 1
            },
            {
                "question_number": "3d",
                "question_text": "Choose the grammatically correct sentence:",
                "options": [
                    {"id": "i", "text": "I am writing to inform you that your application has been received."},
                    {"id": "ii", "text": "I write to inform you that your application is received."},
                    {"id": "iii", "text": "I am writing for informing you that your application has been received."},
                    {"id": "iv", "text": "I write for inform you that your application was received."}
                ],
                "correct_answer": "i",
                "marks": 1
            },
            {
                "question_number": "3e",
                "question_text": "Choose the grammatically correct sentence:",
                "options": [
                    {"id": "i", "text": "Attached herewith please find the requested documents."},
                    {"id": "ii", "text": "Please find attached the requested documents."},
                    {"id": "iii", "text": "The requested documents are attached herewith."},
                    {"id": "iv", "text": "Requested documents attached herewith kindly find."}
                ],
                "correct_answer": "ii",
                "marks": 1
            }
        ]
        
        # Add all grammar questions
        for q_data in grammar_questions_1 + grammar_questions_2 + grammar_questions_3:
            question = Question(
                section_id=section_a.id,
                question_number=q_data["question_number"],
                question_type="mcq",
                question_text=q_data["question_text"],
                options=q_data["options"],
                correct_answer=q_data["correct_answer"],
                marks=q_data["marks"],
                difficulty="medium",
                is_active=True
            )
            db.add(question)
        
        # Section B: Reading Comprehension
        reading_passage = """In today's competitive business environment, effective communication skills are essential for professional success. Companies increasingly value employees who can articulate ideas clearly, write professional emails, and collaborate effectively with diverse teams. Research shows that poor communication costs businesses millions annually through misunderstandings, delays, and reduced productivity.

Strong written communication ensures that messages are understood correctly the first time, reducing the need for clarification and saving valuable time. Meanwhile, verbal communication skills help build relationships with clients and colleagues, facilitate smooth negotiations, and contribute to a positive workplace culture. Employees who master both forms of communication often advance more quickly in their careers.

Furthermore, in our globalized economy, the ability to communicate across cultural boundaries has become increasingly important. Professionals must be sensitive to different communication styles and adapt their approach accordingly."""
        
        section_b = TestSection(
            test_id=english_test.id,
            title="Section B: Reading Comprehension",
            instructions="Read the following passage and answer the questions below. (10 marks, 2 marks each)",
            passage=reading_passage,
            total_marks=10,
            order=2
        )
        db.add(section_b)
        await db.flush()
        
        reading_questions = [
            {
                "question_number": "1",
                "question_text": "According to the passage, poor communication costs businesses millions annually through:",
                "options": [
                    {"id": "i", "text": "Misunderstandings and delays only"},
                    {"id": "ii", "text": "Reduced productivity only"},
                    {"id": "iii", "text": "Misunderstandings, delays, and reduced productivity"},
                    {"id": "iv", "text": "Employee turnover and conflicts"}
                ],
                "correct_answer": "iii",
                "marks": 2
            },
            {
                "question_number": "2",
                "question_text": "What is the main benefit of strong written communication mentioned in the passage?",
                "options": [
                    {"id": "i", "text": "It helps build relationships with clients"},
                    {"id": "ii", "text": "It ensures messages are understood correctly the first time"},
                    {"id": "iii", "text": "It contributes to positive workplace culture"},
                    {"id": "iv", "text": "It facilitates smooth negotiations"}
                ],
                "correct_answer": "ii",
                "marks": 2
            },
            {
                "question_number": "3",
                "question_text": "Which TWO benefits of good verbal communication skills are mentioned in the passage?",
                "options": [
                    {"id": "i", "text": "Helps build relationships and facilitates negotiations"},
                    {"id": "ii", "text": "Saves time and reduces costs"},
                    {"id": "iii", "text": "Improves written communication and teamwork"},
                    {"id": "iv", "text": "Increases salary and promotions"}
                ],
                "correct_answer": "i",
                "marks": 2
            },
            {
                "question_number": "4",
                "question_text": "Why is cross-cultural communication important according to the passage?",
                "options": [
                    {"id": "i", "text": "Because companies are hiring more international employees"},
                    {"id": "ii", "text": "Because English is not everyone's first language"},
                    {"id": "iii", "text": "Because of the globalized economy requiring communication across cultural boundaries"},
                    {"id": "iv", "text": "Because it helps reduce business costs"}
                ],
                "correct_answer": "iii",
                "marks": 2
            },
            {
                "question_number": "5",
                "question_text": "What does the passage suggest about employees who master both written and verbal communication?",
                "options": [
                    {"id": "i", "text": "They earn higher salaries"},
                    {"id": "ii", "text": "They often advance more quickly in their careers"},
                    {"id": "iii", "text": "They become better managers"},
                    {"id": "iv", "text": "They work in international companies"}
                ],
                "correct_answer": "ii",
                "marks": 2
            }
        ]
        
        for q_data in reading_questions:
            question = Question(
                section_id=section_b.id,
                question_number=q_data["question_number"],
                question_type="mcq",
                question_text=q_data["question_text"],
                options=q_data["options"],
                correct_answer=q_data["correct_answer"],
                passage_id="passage-1",
                marks=q_data["marks"],
                difficulty="medium",
                is_active=True
            )
            db.add(question)
        
        print("✅ English Proficiency Test created with 20 questions!")
        
        # ========== LOGICAL REASONING TEST ==========
        logical_test = Test(
            title="Logical Reasoning Test",
            description="Test your logical and analytical reasoning abilities with number series and deduction problems.",
            category="Logical",
            assessment_type="standalone_assessment",
            duration_minutes=45,
            passing_marks=8,  # 53% of 15
            total_questions=10,
            total_marks=15,
            is_published=True,
            is_active=True,
            enable_tab_switch_detection=True,
            max_tab_switches_allowed=3
        )
        db.add(logical_test)
        await db.flush()
        
        # Section A: Number Series
        section_number = TestSection(
            test_id=logical_test.id,
            title="Section A: Number Series",
            instructions="Complete the following number series by finding the missing number. (5 marks, 1 mark each)",
            total_marks=5,
            order=1
        )
        db.add(section_number)
        await db.flush()
        
        number_series_questions = [
            {
                "question_number": "1",
                "question_text": "5, 10, 20, 40, 80, __",
                "options": [
                    {"id": "a", "text": "120"},
                    {"id": "b", "text": "140"},
                    {"id": "c", "text": "160"},
                    {"id": "d", "text": "180"}
                ],
                "correct_answer": "c",  # 160 (doubles each time)
                "marks": 1
            },
            {
                "question_number": "2",
                "question_text": "2, 5, 10, 17, 26, __",
                "options": [
                    {"id": "a", "text": "35"},
                    {"id": "b", "text": "37"},
                    {"id": "c", "text": "39"},
                    {"id": "d", "text": "41"}
                ],
                "correct_answer": "b",  # 37 (differences: 3,5,7,9,11)
                "marks": 1
            },
            {
                "question_number": "3",
                "question_text": "1, 4, 9, 16, 25, __",
                "options": [
                    {"id": "a", "text": "30"},
                    {"id": "b", "text": "32"},
                    {"id": "c", "text": "36"},
                    {"id": "d", "text": "49"}
                ],
                "correct_answer": "c",  # 36 (perfect squares)
                "marks": 1
            },
            {
                "question_number": "4",
                "question_text": "2, 6, 12, 20, 30, 42, __",
                "options": [
                    {"id": "a", "text": "54"},
                    {"id": "b", "text": "56"},
                    {"id": "c", "text": "58"},
                    {"id": "d", "text": "60"}
                ],
                "correct_answer": "b",  # 56 (n*(n+1): 1*2, 2*3, 3*4...)
                "marks": 1
            },
            {
                "question_number": "5",
                "question_text": "1, 2, 6, 24, 120, __",
                "options": [
                    {"id": "a", "text": "240"},
                    {"id": "b", "text": "480"},
                    {"id": "c", "text": "600"},
                    {"id": "d", "text": "720"}
                ],
                "correct_answer": "d",  # 720 (factorials: 1!, 2!, 3!, 4!, 5!, 6!)
                "marks": 1
            }
        ]
        
        for q_data in number_series_questions:
            question = Question(
                section_id=section_number.id,
                question_number=q_data["question_number"],
                question_type="mcq",
                question_text=q_data["question_text"],
                options=q_data["options"],
                correct_answer=q_data["correct_answer"],
                marks=q_data["marks"],
                difficulty="medium",
                is_active=True
            )
            db.add(question)
        
        # Section B: Logical Deduction
        section_deduction = TestSection(
            test_id=logical_test.id,
            title="Section B: Logical Deduction",
            instructions="Choose the correct answer based on logical reasoning. (10 marks, 2 marks each)",
            total_marks=10,
            order=2
        )
        db.add(section_deduction)
        await db.flush()
        
        deduction_questions = [
            {
                "question_number": "1",
                "question_text": "All managers are employees. Some employees are engineers. Which conclusion is definitely true?",
                "options": [
                    {"id": "a", "text": "All engineers are managers"},
                    {"id": "b", "text": "Some managers are engineers"},
                    {"id": "c", "text": "All employees are managers"},
                    {"id": "d", "text": "None of the above can be concluded"}
                ],
                "correct_answer": "d",
                "marks": 2
            },
            {
                "question_number": "2",
                "question_text": "If it rains, the ground gets wet. The ground is wet. What can we conclude?",
                "options": [
                    {"id": "a", "text": "It must have rained"},
                    {"id": "b", "text": "It may have rained"},
                    {"id": "c", "text": "It did not rain"},
                    {"id": "d", "text": "Cannot say anything"}
                ],
                "correct_answer": "b",  # Affirming the consequent - it MAY have rained
                "marks": 2
            },
            {
                "question_number": "3",
                "question_text": "In a family: D is grandmother of A and mother of B. C is wife of B and mother of F. F is granddaughter of D. What is the relationship between A and F?",
                "options": [
                    {"id": "a", "text": "Sisters"},
                    {"id": "b", "text": "Brothers"},
                    {"id": "c", "text": "Cousins"},
                    {"id": "d", "text": "Cannot be determined"}
                ],
                "correct_answer": "d",  # A's parent unknown, could be cousins or siblings
                "marks": 2
            },
            {
                "question_number": "4",
                "question_text": "Five friends P, Q, R, S, T are sitting in a row. P and Q are sitting together. R is sitting at one end. T is not sitting next to Q. S is sitting to the left of P. Who is sitting in the middle?",
                "options": [
                    {"id": "a", "text": "P"},
                    {"id": "b", "text": "Q"},
                    {"id": "c", "text": "S"},
                    {"id": "d", "text": "T"}
                ],
                "correct_answer": "a",  # R-T-S-P-Q or Q-P-S-T-R, P is middle
                "marks": 2
            },
            {
                "question_number": "5",
                "question_text": "If CAT = 24, DOG = 26, then BIRD = ?",
                "options": [
                    {"id": "a", "text": "34"},
                    {"id": "b", "text": "36"},
                    {"id": "c", "text": "33"},
                    {"id": "d", "text": "40"}
                ],
                "correct_answer": "c",  # C(3)+A(1)+T(20)=24, D(4)+O(15)+G(7)=26, B(2)+I(9)+R(18)+D(4)=33
                "marks": 2
            }
        ]
        
        for q_data in deduction_questions:
            question = Question(
                section_id=section_deduction.id,
                question_number=q_data["question_number"],
                question_type="mcq",
                question_text=q_data["question_text"],
                options=q_data["options"],
                correct_answer=q_data["correct_answer"],
                marks=q_data["marks"],
                difficulty="hard",
                is_active=True
            )
            db.add(question)
        
        print("✅ Logical Reasoning Test created with 10 questions!")
        
        await db.commit()
        
        print("\n🎉 Sample assessments created successfully!")
        print("\n📋 Summary:")
        print("   1. English Proficiency Test")
        print("      - Category: English")
        print("      - Duration: 60 mins | Questions: 20 | Marks: 25")
        print("      - Sections: Grammar (15 marks), Reading (10 marks)")
        print("      - Passing: 15 marks (60%)")
        print("")
        print("   2. Logical Reasoning Test")
        print("      - Category: Logical")
        print("      - Duration: 45 mins | Questions: 10 | Marks: 15")
        print("      - Sections: Number Series (5 marks), Deduction (10 marks)")
        print("      - Passing: 8 marks (53%)")


if __name__ == "__main__":
    asyncio.run(seed_assessments())

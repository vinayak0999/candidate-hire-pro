"""
Script to create the English Proficiency & Logical Reasoning Test in production database.
Run this script from the backend directory with:
    python -m scripts.create_production_assessment
"""
import asyncio
from app.database import engine, get_db, async_session_maker
from app.models.test import Test, TestSection, Question
from sqlalchemy import text
from datetime import datetime, timezone


async def create_assessment():
    async with async_session_maker() as db:
        try:
            # ========== CREATE ASSESSMENT ==========
            assessment = Test(
                title="English & Logical Test",
                description="A comprehensive assessment testing grammar, vocabulary, reading comprehension, number series, and logical deduction skills.",
                category="English",
                assessment_type="standalone",
                duration_minutes=45,
                total_questions=30,
                total_marks=40,
                passing_marks=24,  # 60% pass rate
                is_active=True,
                is_published=True,
                enable_tab_switch_detection=True,
                max_tab_switches_allowed=3,
                created_at=datetime.now(timezone.utc)
            )
            db.add(assessment)
            await db.flush()  # Get the ID
            
            print(f"Created assessment: {assessment.title} (ID: {assessment.id})")
            
            # ========== SECTION 1: GRAMMAR & VOCABULARY (15 marks) ==========
            section1 = TestSection(
                test_id=assessment.id,
                title="Section A: Grammar & Vocabulary",
                instructions="Choose the correct option to complete each sentence or identify errors. Each question carries 1 mark.",
                total_marks=15,
                order=1,
                passage=None
            )
            db.add(section1)
            await db.flush()
            
            # Question 1a-1e: Complete the sentence
            grammar_q1 = [
                {
                    "number": "1a",
                    "text": "The project ________ by next Friday.",
                    "options": [
                        {"id": "i", "text": "will complete"},
                        {"id": "ii", "text": "will be completed"},
                        {"id": "iii", "text": "completes"},
                        {"id": "iv", "text": "completing"}
                    ],
                    "answer": "ii"
                },
                {
                    "number": "1b",
                    "text": "Neither the manager nor the employees ________ present at the meeting.",
                    "options": [
                        {"id": "i", "text": "was"},
                        {"id": "ii", "text": "were"},
                        {"id": "iii", "text": "is"},
                        {"id": "iv", "text": "are"}
                    ],
                    "answer": "ii"
                },
                {
                    "number": "1c",
                    "text": "She has been working here ________ five years.",
                    "options": [
                        {"id": "i", "text": "since"},
                        {"id": "ii", "text": "for"},
                        {"id": "iii", "text": "from"},
                        {"id": "iv", "text": "during"}
                    ],
                    "answer": "ii"
                },
                {
                    "number": "1d",
                    "text": "The report needs to be submitted ________ you leave today.",
                    "options": [
                        {"id": "i", "text": "before"},
                        {"id": "ii", "text": "until"},
                        {"id": "iii", "text": "unless"},
                        {"id": "iv", "text": "while"}
                    ],
                    "answer": "i"
                },
                {
                    "number": "1e",
                    "text": "This is the most ________ solution we've found so far.",
                    "options": [
                        {"id": "i", "text": "effective"},
                        {"id": "ii", "text": "more effective"},
                        {"id": "iii", "text": "effectiveness"},
                        {"id": "iv", "text": "effectively"}
                    ],
                    "answer": "i"
                }
            ]
            
            # Question 2a-2e: Identify errors
            grammar_q2 = [
                {
                    "number": "2a",
                    "text": "Identify the error: 'The team have completed their assignment yesterday.'",
                    "options": [
                        {"id": "i", "text": "have → had"},
                        {"id": "ii", "text": "completed → completing"},
                        {"id": "iii", "text": "their → its"},
                        {"id": "iv", "text": "No error"}
                    ],
                    "answer": "i"
                },
                {
                    "number": "2b",
                    "text": "Identify the error: 'She don't have any experience in this field.'",
                    "options": [
                        {"id": "i", "text": "don't → doesn't"},
                        {"id": "ii", "text": "have → has"},
                        {"id": "iii", "text": "any → some"},
                        {"id": "iv", "text": "No error"}
                    ],
                    "answer": "i"
                },
                {
                    "number": "2c",
                    "text": "Identify the error: 'Please send the documents to John and myself.'",
                    "options": [
                        {"id": "i", "text": "send → sent"},
                        {"id": "ii", "text": "to → for"},
                        {"id": "iii", "text": "myself → me"},
                        {"id": "iv", "text": "No error"}
                    ],
                    "answer": "iii"
                },
                {
                    "number": "2d",
                    "text": "Identify the error: 'The company is looking for someone which can speak three languages.'",
                    "options": [
                        {"id": "i", "text": "is → are"},
                        {"id": "ii", "text": "which → who"},
                        {"id": "iii", "text": "can → could"},
                        {"id": "iv", "text": "No error"}
                    ],
                    "answer": "ii"
                },
                {
                    "number": "2e",
                    "text": "Identify the error: 'He is one of the employee who always meet deadlines.'",
                    "options": [
                        {"id": "i", "text": "is → are"},
                        {"id": "ii", "text": "employee → employees"},
                        {"id": "iii", "text": "meet → meets"},
                        {"id": "iv", "text": "No error"}
                    ],
                    "answer": "ii"
                }
            ]
            
            # Question 3a-3e: Choose correct sentence
            grammar_q3 = [
                {
                    "number": "3a",
                    "text": "Choose the grammatically correct sentence:",
                    "options": [
                        {"id": "i", "text": "Looking forward to hear from you soon."},
                        {"id": "ii", "text": "I look forward to hearing from you soon."},
                        {"id": "iii", "text": "I am looking forward to hear from you soon."},
                        {"id": "iv", "text": "Looking forward for hearing from you soon."}
                    ],
                    "answer": "ii"
                },
                {
                    "number": "3b",
                    "text": "Choose the grammatically correct sentence:",
                    "options": [
                        {"id": "i", "text": "Kindly do the needful at the earliest."},
                        {"id": "ii", "text": "Please take necessary action as soon as possible."},
                        {"id": "iii", "text": "Do what is needed urgently."},
                        {"id": "iv", "text": "Please be doing the necessary."}
                    ],
                    "answer": "ii"
                },
                {
                    "number": "3c",
                    "text": "Choose the grammatically correct sentence:",
                    "options": [
                        {"id": "i", "text": "The meeting will be held at 10 AM in the morning."},
                        {"id": "ii", "text": "The meeting will be held at 10 o'clock AM."},
                        {"id": "iii", "text": "The meeting will be held at 10 AM."},
                        {"id": "iv", "text": "The meeting will be held at 10 in the morning AM."}
                    ],
                    "answer": "iii"
                },
                {
                    "number": "3d",
                    "text": "Choose the grammatically correct sentence:",
                    "options": [
                        {"id": "i", "text": "I am writing to inform you that your application has been received."},
                        {"id": "ii", "text": "I write to inform you that your application is received."},
                        {"id": "iii", "text": "I am writing for informing you that your application has been received."},
                        {"id": "iv", "text": "I write for inform you that your application was received."}
                    ],
                    "answer": "i"
                },
                {
                    "number": "3e",
                    "text": "Choose the grammatically correct sentence:",
                    "options": [
                        {"id": "i", "text": "Attached herewith please find the requested documents."},
                        {"id": "ii", "text": "Please find attached the requested documents."},
                        {"id": "iii", "text": "The requested documents are attached herewith."},
                        {"id": "iv", "text": "Requested documents attached herewith kindly find."}
                    ],
                    "answer": "ii"
                }
            ]
            
            # Add all grammar questions
            for q in grammar_q1 + grammar_q2 + grammar_q3:
                question = Question(
                    section_id=section1.id,
                    question_number=q["number"],
                    question_type="mcq",
                    question_text=q["text"],
                    options=q["options"],
                    correct_answer=q["answer"],
                    marks=1.0,
                    difficulty="medium",
                    is_active=True
                )
                db.add(question)
            
            print(f"Added Section A: Grammar & Vocabulary (15 questions)")
            
            # ========== SECTION 2: READING COMPREHENSION (10 marks) ==========
            reading_passage = """In today's competitive business environment, effective communication skills are essential for professional success. Companies increasingly value employees who can articulate ideas clearly, write professional emails, and collaborate effectively with diverse teams. Research shows that poor communication costs businesses millions annually through misunderstandings, delays, and reduced productivity.

Strong written communication ensures that messages are understood correctly the first time, reducing the need for clarification and saving valuable time. Meanwhile, verbal communication skills help build relationships with clients and colleagues, facilitate smooth negotiations, and contribute to a positive workplace culture. Employees who master both forms of communication often advance more quickly in their careers.

Furthermore, in our globalized economy, the ability to communicate across cultural boundaries has become increasingly important. Professionals must be sensitive to different communication styles and adapt their approach accordingly."""
            
            section2 = TestSection(
                test_id=assessment.id,
                title="Section B: Reading Comprehension",
                instructions="Read the following passage carefully and answer the questions below. Each question carries 2 marks.",
                total_marks=10,
                order=2,
                passage=reading_passage
            )
            db.add(section2)
            await db.flush()
            
            reading_questions = [
                {
                    "number": "4",
                    "text": "According to the passage, poor communication costs businesses millions annually through:",
                    "options": [
                        {"id": "i", "text": "Misunderstandings and delays only"},
                        {"id": "ii", "text": "Reduced productivity only"},
                        {"id": "iii", "text": "Misunderstandings, delays, and reduced productivity"},
                        {"id": "iv", "text": "Employee turnover and conflicts"}
                    ],
                    "answer": "iii",
                    "marks": 2.0
                },
                {
                    "number": "5",
                    "text": "What is the main benefit of strong written communication mentioned in the passage?",
                    "options": [
                        {"id": "i", "text": "It helps build relationships with clients"},
                        {"id": "ii", "text": "It ensures messages are understood correctly the first time"},
                        {"id": "iii", "text": "It contributes to positive workplace culture"},
                        {"id": "iv", "text": "It facilitates smooth negotiations"}
                    ],
                    "answer": "ii",
                    "marks": 2.0
                },
                {
                    "number": "6",
                    "text": "Which TWO benefits of good verbal communication skills are mentioned in the passage?",
                    "options": [
                        {"id": "i", "text": "Helps build relationships and facilitates negotiations"},
                        {"id": "ii", "text": "Saves time and reduces costs"},
                        {"id": "iii", "text": "Improves written communication and teamwork"},
                        {"id": "iv", "text": "Increases salary and promotions"}
                    ],
                    "answer": "i",
                    "marks": 2.0
                },
                {
                    "number": "7",
                    "text": "Why is cross-cultural communication important according to the passage?",
                    "options": [
                        {"id": "i", "text": "Because companies are hiring more international employees"},
                        {"id": "ii", "text": "Because English is not everyone's first language"},
                        {"id": "iii", "text": "Because of the globalized economy requiring communication across cultural boundaries"},
                        {"id": "iv", "text": "Because it helps reduce business costs"}
                    ],
                    "answer": "iii",
                    "marks": 2.0
                },
                {
                    "number": "8",
                    "text": "What does the passage suggest about employees who master both written and verbal communication?",
                    "options": [
                        {"id": "i", "text": "They earn higher salaries"},
                        {"id": "ii", "text": "They often advance more quickly in their careers"},
                        {"id": "iii", "text": "They become better managers"},
                        {"id": "iv", "text": "They work in international companies"}
                    ],
                    "answer": "ii",
                    "marks": 2.0
                }
            ]
            
            for q in reading_questions:
                question = Question(
                    section_id=section2.id,
                    question_number=q["number"],
                    question_type="mcq",
                    question_text=q["text"],
                    options=q["options"],
                    correct_answer=q["answer"],
                    marks=q["marks"],
                    difficulty="medium",
                    is_active=True
                )
                db.add(question)
            
            print(f"Added Section B: Reading Comprehension (5 questions)")
            
            # ========== SECTION 3: NUMBER SERIES (5 marks) ==========
            section3 = TestSection(
                test_id=assessment.id,
                title="Section C: Number Series",
                instructions="Complete the following number series by finding the missing number. Each question carries 1 mark.",
                total_marks=5,
                order=3,
                passage=None
            )
            db.add(section3)
            await db.flush()
            
            number_series = [
                {
                    "number": "9",
                    "text": "5, 10, 20, 40, 80, __",
                    "options": [
                        {"id": "a", "text": "120"},
                        {"id": "b", "text": "140"},
                        {"id": "c", "text": "160"},
                        {"id": "d", "text": "180"}
                    ],
                    "answer": "c"
                },
                {
                    "number": "10",
                    "text": "2, 5, 10, 17, 26, __",
                    "options": [
                        {"id": "a", "text": "35"},
                        {"id": "b", "text": "37"},
                        {"id": "c", "text": "39"},
                        {"id": "d", "text": "41"}
                    ],
                    "answer": "b"
                },
                {
                    "number": "11",
                    "text": "1, 4, 9, 16, 25, __",
                    "options": [
                        {"id": "a", "text": "30"},
                        {"id": "b", "text": "32"},
                        {"id": "c", "text": "36"},
                        {"id": "d", "text": "49"}
                    ],
                    "answer": "c"
                },
                {
                    "number": "12",
                    "text": "2, 6, 12, 20, 30, 42, __",
                    "options": [
                        {"id": "a", "text": "54"},
                        {"id": "b", "text": "56"},
                        {"id": "c", "text": "58"},
                        {"id": "d", "text": "60"}
                    ],
                    "answer": "b"
                },
                {
                    "number": "13",
                    "text": "1, 2, 6, 24, 120, __",
                    "options": [
                        {"id": "a", "text": "240"},
                        {"id": "b", "text": "480"},
                        {"id": "c", "text": "600"},
                        {"id": "d", "text": "720"}
                    ],
                    "answer": "d"
                }
            ]
            
            for q in number_series:
                question = Question(
                    section_id=section3.id,
                    question_number=q["number"],
                    question_type="mcq",
                    question_text=q["text"],
                    options=q["options"],
                    correct_answer=q["answer"],
                    marks=1.0,
                    difficulty="medium",
                    is_active=True
                )
                db.add(question)
            
            print(f"Added Section C: Number Series (5 questions)")
            
            # ========== SECTION 4: LOGICAL DEDUCTION (10 marks) ==========
            section4 = TestSection(
                test_id=assessment.id,
                title="Section D: Logical Deduction",
                instructions="Choose the correct answer based on logical reasoning. Each question carries 2 marks.",
                total_marks=10,
                order=4,
                passage=None
            )
            db.add(section4)
            await db.flush()
            
            logical_questions = [
                {
                    "number": "14",
                    "text": "All managers are employees. Some employees are engineers. Which conclusion is definitely true?",
                    "options": [
                        {"id": "a", "text": "All engineers are managers"},
                        {"id": "b", "text": "Some managers are engineers"},
                        {"id": "c", "text": "All employees are managers"},
                        {"id": "d", "text": "None of the above can be concluded"}
                    ],
                    "answer": "d",
                    "marks": 2.0
                },
                {
                    "number": "15",
                    "text": "If it rains, the ground gets wet. The ground is wet. What can we conclude?",
                    "options": [
                        {"id": "a", "text": "It must have rained"},
                        {"id": "b", "text": "It may have rained"},
                        {"id": "c", "text": "It did not rain"},
                        {"id": "d", "text": "Cannot say anything"}
                    ],
                    "answer": "b",
                    "marks": 2.0
                },
                {
                    "number": "16",
                    "text": "In a family of six persons A, B, C, D, E and F: There are two married couples. D is grandmother of A and mother of B. C is wife of B and mother of F. F is granddaughter of D. What is the relationship between A and F?",
                    "options": [
                        {"id": "a", "text": "Sisters"},
                        {"id": "b", "text": "Brothers"},
                        {"id": "c", "text": "Cousins"},
                        {"id": "d", "text": "Cannot be determined"}
                    ],
                    "answer": "a",
                    "marks": 2.0
                },
                {
                    "number": "17",
                    "text": "Five friends P, Q, R, S, and T are sitting in a row. P and Q are sitting together. R is sitting at one end. T is not sitting next to Q. S is sitting to the left of P. Who is sitting in the middle?",
                    "options": [
                        {"id": "a", "text": "P"},
                        {"id": "b", "text": "Q"},
                        {"id": "c", "text": "S"},
                        {"id": "d", "text": "T"}
                    ],
                    "answer": "b",
                    "marks": 2.0
                },
                {
                    "number": "18",
                    "text": "If CAT = 24, DOG = 26, then what is BIRD = ?",
                    "options": [
                        {"id": "a", "text": "34"},
                        {"id": "b", "text": "36"},
                        {"id": "c", "text": "33"},
                        {"id": "d", "text": "40"}
                    ],
                    "answer": "c",
                    "marks": 2.0
                }
            ]
            
            for q in logical_questions:
                question = Question(
                    section_id=section4.id,
                    question_number=q["number"],
                    question_type="mcq",
                    question_text=q["text"],
                    options=q["options"],
                    correct_answer=q["answer"],
                    marks=q["marks"],
                    difficulty="hard",
                    is_active=True
                )
                db.add(question)
            
            print(f"Added Section D: Logical Deduction (5 questions)")
            
            # ========== COMMIT ==========
            await db.commit()
            
            print("\n" + "="*50)
            print("ASSESSMENT CREATED SUCCESSFULLY!")
            print("="*50)
            print(f"Title: {assessment.title}")
            print(f"ID: {assessment.id}")
            print(f"Total Questions: 30")
            print(f"Total Marks: 40")
            print(f"Duration: 45 minutes")
            print(f"Passing Marks: 24 (60%)")
            print("="*50)
            
        except Exception as e:
            await db.rollback()
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(create_assessment())

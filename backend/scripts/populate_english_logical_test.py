"""
Populate English & Logical Test with questions from Qes&ans.md
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import json

DATABASE_URL = "postgresql+asyncpg://postgres.rmysstjbjaaqctbbswmj:TechRevolution%402050@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

async def populate_assessment():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get assessment ID 14
        result = await session.execute(text("SELECT id, title FROM tests WHERE id = 14"))
        assessment = result.fetchone()
        print(f"Assessment: {assessment}")
        
        # Delete existing sections and questions first (using correct user_answers cascade)
        await session.execute(text("""
            DELETE FROM user_answers WHERE question_id IN (
                SELECT id FROM questions WHERE section_id IN (
                    SELECT id FROM test_sections WHERE test_id = 14
                )
            )
        """))
        await session.execute(text("DELETE FROM questions WHERE section_id IN (SELECT id FROM test_sections WHERE test_id = 14)"))
        await session.execute(text("DELETE FROM test_sections WHERE test_id = 14"))
        
        # SECTION 1: ENGLISH - GRAMMAR & VOCABULARY (15 marks)
        result = await session.execute(text("""
            INSERT INTO test_sections (test_id, title, instructions, "order")
            VALUES (14, 'Grammar & Vocabulary', 'Choose correct options, identify errors, and select grammatically correct sentences', 1)
            RETURNING id
        """))
        section1_id = result.fetchone()[0]
        print(f"Created section 1: Grammar & Vocabulary (ID: {section1_id})")
        
        # Q1: Fill in blanks (5 questions)
        q1_questions = [
            ("Not until the final results were announced ________ the magnitude of their achievement.", 
             ["they realized", "did they realize", "they did realize", "realized they"], "did they realize"),
            ("The contract stipulates that all disputes ________ through arbitration rather than litigation.",
             ["are resolved", "be resolved", "will be resolved", "would be resolved"], "be resolved"),
            ("________ the committee's recommendations, the policy remains unchanged.",
             ["Contrary to", "Despite of", "Irregardless of", "Notwithstanding of"], "Contrary to"),
            ("Had the investors ________ of the impending crisis, they would have withdrawn their funds.",
             ["been apprised", "apprised", "being apprised", "apprise"], "been apprised"),
            ("The phenomenon, ________ extensively in recent studies, continues to baffle researchers.",
             ["that has been documented", "which documenting", "having been documented", "been documented"], "having been documented"),
        ]
        
        for q_text, options, answer in q1_questions:
            await session.execute(text("""
                INSERT INTO questions (section_id, question_type, question_text, options, correct_answer, marks)
                VALUES (:section_id, 'mcq', :text, :options, :answer, 1)
            """), {"section_id": section1_id, "text": q_text, "options": json.dumps(options), "answer": answer})
        print(f"  Added 5 fill-in-blank questions")
        
        # Q2: Identify errors (5 questions)
        q2_questions = [
            ("The data compiled from various sources suggest that the hypothesis require further validation.",
             ["data → datas", "suggest → suggests", "require → requires", "No error"], "require → requires"),
            ("Neither the CEO nor the board members was aware of the discrepancies in the financial statements.",
             ["Neither → Either", "was → were", "discrepancies → discrepancy", "No error"], "was → were"),
            ("The committee has recommended that each department submits its quarterly report by Friday.",
             ["has → have", "submits → submit", "its → their", "No error"], "submits → submit"),
            ("Scarcely had the merger been announced than the stock prices began to fluctuate dramatically.",
             ["had → did", "than → when", "began → begun", "No error"], "than → when"),
            ("The phenomenon of urban migration, coupled with inadequate infrastructure, have created unprecedented challenges.",
             ["of → for", "coupled → coupling", "have → has", "No error"], "have → has"),
        ]
        
        for q_text, options, answer in q2_questions:
            await session.execute(text("""
                INSERT INTO questions (section_id, question_type, question_text, options, correct_answer, marks)
                VALUES (:section_id, 'mcq', :text, :options, :answer, 1)
            """), {"section_id": section1_id, "text": "Identify the error: " + q_text, "options": json.dumps(options), "answer": answer})
        print(f"  Added 5 error identification questions")
        
        # Q3: Correct sentence (5 questions)
        q3_questions = [
            ("Choose the grammatically correct sentence:",
             ["Had I known about the implications, I would not have proceeded with the merger.",
              "Had I known about the implications, I would not proceed with the merger.",
              "If I had known about the implications, I would not proceeded with the merger.",
              "If I would have known about the implications, I would not have proceeded with the merger."],
             "Had I known about the implications, I would not have proceeded with the merger."),
            ("Choose the grammatically correct sentence:",
             ["Between you and I, this proposal seems unfeasible.",
              "Between you and me, this proposal seems unfeasible.",
              "Between you and myself, this proposal seems unfeasible.",
              "Between yourself and I, this proposal seems unfeasible."],
             "Between you and me, this proposal seems unfeasible."),
            ("Choose the grammatically correct sentence:",
             ["The number of applicants have increased significantly this year.",
              "The number of applicants has increased significantly this year.",
              "A number of applicants has increased significantly this year.",
              "The number of applicant have increased significantly this year."],
             "The number of applicants has increased significantly this year."),
            ("Choose the grammatically correct sentence:",
             ["Whoever completes the task first will receive the bonus.",
              "Whomever completes the task first will receive the bonus.",
              "Whoever complete the task first will receive the bonus.",
              "Who ever completes the task first will receive the bonus."],
             "Whoever completes the task first will receive the bonus."),
            ("Choose the grammatically correct sentence:",
             ["The committee comprising of five members meet weekly.",
              "The committee composed of five members meets weekly.",
              "The committee comprised of five members meet weekly.",
              "The committee composing of five members meets weekly."],
             "The committee composed of five members meets weekly."),
        ]
        
        for q_text, options, answer in q3_questions:
            await session.execute(text("""
                INSERT INTO questions (section_id, question_type, question_text, options, correct_answer, marks)
                VALUES (:section_id, 'mcq', :text, :options, :answer, 1)
            """), {"section_id": section1_id, "text": q_text, "options": json.dumps(options), "answer": answer})
        print(f"  Added 5 correct sentence questions")
        
        # SECTION 2: READING COMPREHENSION (10 marks) - WITH PASSAGE
        passage = """In today's competitive business environment, effective communication skills are essential for professional success. Companies increasingly value employees who can articulate ideas clearly, write professional emails, and collaborate effectively with diverse teams. Research shows that poor communication costs businesses millions annually through misunderstandings, delays, and reduced productivity.

Strong written communication ensures that messages are understood correctly the first time, reducing the need for clarification and saving valuable time. Meanwhile, verbal communication skills help build relationships with clients and colleagues, facilitate smooth negotiations, and contribute to a positive workplace culture. Employees who master both forms of communication often advance more quickly in their careers.

Furthermore, in our globalized economy, the ability to communicate across cultural boundaries has become increasingly important. Professionals must be sensitive to different communication styles and adapt their approach accordingly."""

        result = await session.execute(text("""
            INSERT INTO test_sections (test_id, title, instructions, passage, "order")
            VALUES (14, 'Reading Comprehension', 'Read the following passage and answer the questions below:', :passage, 2)
            RETURNING id
        """), {"passage": passage})
        section2_id = result.fetchone()[0]
        print(f"Created section 2: Reading Comprehension (ID: {section2_id})")
        
        rc_questions = [
            ("According to the passage, poor communication costs businesses millions annually through:",
             ["Misunderstandings and delays only", "Reduced productivity only", 
              "Misunderstandings, delays, and reduced productivity", "Employee turnover and conflicts"],
             "Misunderstandings, delays, and reduced productivity"),
            ("What is the main benefit of strong written communication mentioned in the passage?",
             ["It helps build relationships with clients", "It ensures messages are understood correctly the first time",
              "It contributes to positive workplace culture", "It facilitates smooth negotiations"],
             "It ensures messages are understood correctly the first time"),
            ("Which TWO benefits of good verbal communication skills are mentioned in the passage?",
             ["Helps build relationships and facilitates negotiations", "Saves time and reduces costs",
              "Improves written communication and teamwork", "Increases salary and promotions"],
             "Helps build relationships and facilitates negotiations"),
            ("Why is cross-cultural communication important according to the passage?",
             ["Because companies are hiring more international employees", "Because English is not everyone's first language",
              "Because of the globalized economy requiring communication across cultural boundaries", "Because it helps reduce business costs"],
             "Because of the globalized economy requiring communication across cultural boundaries"),
            ("What does the passage suggest about employees who master both written and verbal communication?",
             ["They earn higher salaries", "They often advance more quickly in their careers",
              "They become better managers", "They work in international companies"],
             "They often advance more quickly in their careers"),
        ]
        
        for q_text, options, answer in rc_questions:
            await session.execute(text("""
                INSERT INTO questions (section_id, question_type, question_text, options, correct_answer, marks)
                VALUES (:section_id, 'mcq', :text, :options, :answer, 2)
            """), {"section_id": section2_id, "text": q_text, "options": json.dumps(options), "answer": answer})
        print(f"  Added 5 reading comprehension questions")
        
        # SECTION 3: NUMBER SERIES (5 marks)
        result = await session.execute(text("""
            INSERT INTO test_sections (test_id, title, instructions, "order")
            VALUES (14, 'Number Series', 'Complete the following number series by finding the missing number.', 3)
            RETURNING id
        """))
        section3_id = result.fetchone()[0]
        print(f"Created section 3: Number Series (ID: {section3_id})")
        
        ns_questions = [
            ("5, 10, 20, 40, 80, __", ["120", "140", "160", "180"], "160"),
            ("2, 5, 10, 17, 26, __", ["35", "37", "39", "41"], "37"),
            ("1, 4, 9, 16, 25, __", ["30", "32", "36", "49"], "36"),
            ("2, 6, 12, 20, 30, 42, __", ["54", "56", "58", "60"], "56"),
            ("1, 2, 6, 24, 120, __", ["240", "480", "600", "720"], "720"),
        ]
        
        for q_text, options, answer in ns_questions:
            await session.execute(text("""
                INSERT INTO questions (section_id, question_type, question_text, options, correct_answer, marks)
                VALUES (:section_id, 'mcq', :text, :options, :answer, 1)
            """), {"section_id": section3_id, "text": q_text, "options": json.dumps(options), "answer": answer})
        print(f"  Added 5 number series questions")
        
        # SECTION 4: LOGICAL DEDUCTION (10 marks)
        result = await session.execute(text("""
            INSERT INTO test_sections (test_id, title, instructions, "order")
            VALUES (14, 'Logical Deduction', 'Choose the correct answer based on logical reasoning.', 4)
            RETURNING id
        """))
        section4_id = result.fetchone()[0]
        print(f"Created section 4: Logical Deduction (ID: {section4_id})")
        
        ld_questions = [
            ("All managers are employees. Some employees are engineers. Which conclusion is definitely true?",
             ["All engineers are managers", "Some managers are engineers", "All employees are managers", "None of the above can be concluded"],
             "None of the above can be concluded"),
            ("If it rains, the ground gets wet. The ground is wet. What can we conclude?",
             ["It must have rained", "It may have rained", "It did not rain", "Cannot say anything"],
             "It may have rained"),
            ("In a family of seven persons P, Q, R, S, T, U and V: There are three married couples. P is the father of R and grandfather of T. Q is the daughter-in-law of P. S is the aunt of T and sister of R. U is the brother-in-law of R. V is the son of U. What is the relationship between T and V?",
             ["Siblings", "Cousins", "Uncle and nephew", "Cannot be determined"],
             "Cousins"),
            ("Five friends P, Q, R, S, and T are sitting in a row. P and Q are sitting together. R is sitting at one end. T is not sitting next to Q. S is sitting to the left of P. Who is sitting in the middle?",
             ["P", "Q", "S", "T"],
             "P"),
            ("If CAT = 24, DOG = 26, then what is BIRD = ?",
             ["34", "36", "33", "40"],
             "33"),
        ]
        
        for q_text, options, answer in ld_questions:
            await session.execute(text("""
                INSERT INTO questions (section_id, question_type, question_text, options, correct_answer, marks)
                VALUES (:section_id, 'mcq', :text, :options, :answer, 2)
            """), {"section_id": section4_id, "text": q_text, "options": json.dumps(options), "answer": answer})
        print(f"  Added 5 logical deduction questions")
        
        # Update assessment totals
        await session.execute(text("""
            UPDATE tests SET 
                total_marks = 40,
                total_questions = 25
            WHERE id = 14
        """))
        
        await session.commit()
        print("\n✅ Assessment populated successfully!")
        print("Total: 4 sections, 25 questions, 40 marks")
        print("- Section 1: Grammar & Vocabulary (15 questions, 15 marks)")
        print("- Section 2: Reading Comprehension with passage (5 questions, 10 marks)")
        print("- Section 3: Number Series (5 questions, 5 marks)")
        print("- Section 4: Logical Deduction (5 questions, 10 marks)")

if __name__ == "__main__":
    asyncio.run(populate_assessment())

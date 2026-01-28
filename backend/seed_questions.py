"""
Seed script to add sample questions to the database
Run with: python -m app.scripts.seed_questions
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session_maker
from app.models.test import Question


SAMPLE_QUESTIONS = [
    # MCQ Questions
    {
        "question_type": "mcq",
        "question_text": "What is the capital of France?",
        "options": ["London", "Berlin", "Paris", "Madrid"],
        "correct_answer": "Paris",
        "marks": 1.0,
        "difficulty": "easy"
    },
    {
        "question_type": "mcq",
        "question_text": "Which planet is known as the Red Planet?",
        "options": ["Venus", "Mars", "Jupiter", "Saturn"],
        "correct_answer": "Mars",
        "marks": 1.0,
        "difficulty": "easy"
    },
    {
        "question_type": "mcq",
        "question_text": "What is 15 × 7?",
        "options": ["95", "105", "115", "85"],
        "correct_answer": "105",
        "marks": 1.0,
        "difficulty": "easy"
    },
    {
        "question_type": "mcq",
        "question_text": "Which programming language is known for its use in web browsers?",
        "options": ["Python", "Java", "JavaScript", "C++"],
        "correct_answer": "JavaScript",
        "marks": 1.0,
        "difficulty": "medium"
    },
    {
        "question_type": "mcq",
        "question_text": "What does HTML stand for?",
        "options": ["HyperText Markup Language", "High Tech Modern Language", "Home Tool Markup Language", "Hyperlink Text Mode Language"],
        "correct_answer": "HyperText Markup Language",
        "marks": 1.0,
        "difficulty": "easy"
    },
    {
        "question_type": "mcq",
        "question_text": "Which data structure follows LIFO principle?",
        "options": ["Queue", "Stack", "Array", "Linked List"],
        "correct_answer": "Stack",
        "marks": 1.0,
        "difficulty": "medium"
    },
    {
        "question_type": "mcq",
        "question_text": "What is the time complexity of binary search?",
        "options": ["O(n)", "O(log n)", "O(n²)", "O(1)"],
        "correct_answer": "O(log n)",
        "marks": 1.0,
        "difficulty": "medium"
    },
    {
        "question_type": "mcq",
        "question_text": "Which SQL keyword is used to retrieve data from a database?",
        "options": ["GET", "FETCH", "SELECT", "RETRIEVE"],
        "correct_answer": "SELECT",
        "marks": 1.0,
        "difficulty": "easy"
    },
    {
        "question_type": "mcq",
        "question_text": "What is the result of 2^10?",
        "options": ["512", "1024", "2048", "256"],
        "correct_answer": "1024",
        "marks": 1.0,
        "difficulty": "medium"
    },
    {
        "question_type": "mcq",
        "question_text": "Which protocol is used for secure web browsing?",
        "options": ["HTTP", "FTP", "HTTPS", "SMTP"],
        "correct_answer": "HTTPS",
        "marks": 1.0,
        "difficulty": "easy"
    },
    # Text Annotation Questions
    {
        "question_type": "text_annotation",
        "question_text": "Read the following passage and identify the main theme:\n\n'The rapid advancement of artificial intelligence has transformed various industries, from healthcare to finance. While AI offers unprecedented opportunities for efficiency and innovation, it also raises important ethical questions about privacy, job displacement, and algorithmic bias.'\n\nDescribe the main theme and supporting points.",
        "marks": 5.0,
        "difficulty": "medium"
    },
    {
        "question_type": "text_annotation",
        "question_text": "Analyze the following code snippet and explain what it does:\n\n```python\ndef mystery(n):\n    if n <= 1:\n        return n\n    return mystery(n-1) + mystery(n-2)\n```\n\nProvide your annotation.",
        "marks": 5.0,
        "difficulty": "medium"
    },
    {
        "question_type": "text_annotation",
        "question_text": "Summarize the key points of the following paragraph:\n\n'Climate change is one of the most pressing challenges of our time. Rising global temperatures are causing ice caps to melt, sea levels to rise, and weather patterns to become more extreme. Scientists agree that human activities, particularly the burning of fossil fuels, are the primary drivers of these changes.'",
        "marks": 5.0,
        "difficulty": "easy"
    },
    # Image Annotation Questions
    {
        "question_type": "image_annotation",
        "question_text": "Identify and label all objects you see in this image. Describe their positions and relationships.",
        "media_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800",
        "marks": 5.0,
        "difficulty": "medium"
    },
    {
        "question_type": "image_annotation",
        "question_text": "Analyze this image and provide annotations for any text, symbols, or important visual elements you observe.",
        "media_url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800",
        "marks": 5.0,
        "difficulty": "medium"
    },
    # Video Annotation Questions
    {
        "question_type": "video_annotation",
        "question_text": "Watch the video and identify the key actions or events. Provide timestamps and descriptions.",
        "media_url": "https://www.w3schools.com/html/mov_bbb.mp4",
        "marks": 10.0,
        "difficulty": "hard"
    },
]


async def seed_questions():
    """Seed the database with sample questions"""
    async with async_session_maker() as db:
        # Check if questions already exist
        from sqlalchemy import select, func
        result = await db.execute(select(func.count(Question.id)))
        count = result.scalar()
        
        if count > 0:
            print(f"Database already has {count} questions. Skipping seed.")
            return
        
        print("Seeding sample questions...")
        for q_data in SAMPLE_QUESTIONS:
            question = Question(**q_data, is_active=True)
            db.add(question)
        
        await db.commit()
        print(f"Successfully added {len(SAMPLE_QUESTIONS)} sample questions!")


if __name__ == "__main__":
    asyncio.run(seed_questions())

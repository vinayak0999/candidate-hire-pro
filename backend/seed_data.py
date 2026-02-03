"""
Seed script to populate the database with mock data
Run with: python -m seed_data
"""
import asyncio
from datetime import datetime, timezone, timedelta
from app.database import async_session_maker, init_db
from app.models import User, Job, Course, CourseEnrollment, Assessment, Badge, JobApplication
from app.models.job import OfferType, JobStatus
from app.models.user import UserRole
from app.services.auth import get_password_hash


async def seed_database():
    await init_db()
    
    async with async_session_maker() as db:
        # Create admin user
        admin = User(
            email="admin@autonex.ai",
            hashed_password=get_password_hash("admin123"),
            name="Admin",
            registration_number="ADMIN001",
            degree="Admin",
            branch="Administration",
            batch="2024",
            college="Autonex",
            role=UserRole.ADMIN,
            neo_pat_score=0,
            solved_easy=0,
            solved_medium=0,
            solved_hard=0,
            badges_count=0,
            super_badges_count=0
        )
        db.add(admin)
        
        # Create demo user
        user = User(
            email="vinayak.shukla@gmail.com",
            hashed_password=get_password_hash("password123"),
            name="Vinayak Ji Shukla",
            registration_number="21BCE7920",
            degree="B.Tech",
            branch="Computer Science and Engineering",
            batch="2025",
            college="CDC - Assessment Portal",
            phone="+91 9876543210",
            avatar_url="/assets/avatar.png",
            neo_pat_score=1324,
            solved_easy=1245,
            solved_medium=1754,
            solved_hard=514,
            badges_count=2473,
            super_badges_count=15482
        )
        db.add(user)
        await db.flush()
        
        # Create jobs
        jobs_data = [
            {"company_name": "Ey India", "role": "Loadr Imagr", "location": "Bangalore", "ctc": 8.6, "offer_type": OfferType.DREAM_CORE},
            {"company_name": "Fujitec India Pvt Ltd.", "role": "Loadr Imagr", "location": None, "ctc": None, "offer_type": OfferType.REGULAR},
            {"company_name": "Indegene", "role": "Loadr Imagr", "location": "Pan India", "ctc": 8, "offer_type": OfferType.REGULAR},
            {"company_name": "Apple India", "role": "Loadr Imagr", "location": "Bangalore", "ctc": None, "offer_type": OfferType.REGULAR},
            {"company_name": "Exasol", "role": "Loadr Imagr", "location": None, "ctc": 10, "offer_type": OfferType.SUPER_DREAM},
            {"company_name": "Enverus", "role": "Loadr Imagr", "location": None, "ctc": None, "offer_type": OfferType.REGULAR},
            {"company_name": "TechMahindra", "role": "Software Engineer", "location": "Hyderabad", "ctc": 7.5, "offer_type": OfferType.REGULAR},
            {"company_name": "TCS", "role": "Developer", "location": "Chennai", "ctc": 6, "offer_type": OfferType.REGULAR},
            {"company_name": "Infosys", "role": "Analyst", "location": "Pune", "ctc": 5.5, "offer_type": OfferType.REGULAR},
            {"company_name": "Wipro", "role": "Engineer", "location": "Bangalore", "ctc": 5, "offer_type": OfferType.REGULAR},
        ]
        
        for job_data in jobs_data:
            job = Job(**job_data, job_type="Full Time", round_date=datetime.now(timezone.utc) + timedelta(days=30))
            db.add(job)
        
        await db.flush()
        
        # Create some job applications for the user
        applications = [
            JobApplication(user_id=user.id, job_id=1, status=JobStatus.APPLIED),
            JobApplication(user_id=user.id, job_id=4, status=JobStatus.NOT_APPLIED),
        ]
        for app in applications:
            db.add(app)
        
        # Create courses
        courses_data = [
            {"title": "Python Programming", "description": "Learn Python from scratch", "duration_hours": 40},
            {"title": "Data Structures & Algorithms", "description": "Master DSA concepts", "duration_hours": 60},
            {"title": "Machine Learning Basics", "description": "Introduction to ML", "duration_hours": 50},
            {"title": "Web Development", "description": "Full stack web development", "duration_hours": 80},
            {"title": "Database Management", "description": "SQL and NoSQL databases", "duration_hours": 30},
        ]
        
        for course_data in courses_data:
            course = Course(**course_data)
            db.add(course)
        
        await db.flush()
        
        # Enroll user in some courses
        enrollments = [
            CourseEnrollment(user_id=user.id, course_id=1, progress=75.0),
            CourseEnrollment(user_id=user.id, course_id=2, progress=30.0),
            CourseEnrollment(user_id=user.id, course_id=3, progress=100.0, completed=True),
        ]
        for enrollment in enrollments:
            db.add(enrollment)
        
        # Create assessments
        assessments_data = [
            {"title": "TCS NQT Mock Test", "company_name": "TCS", "duration_minutes": 90, "total_questions": 60},
            {"title": "Infosys Coding Test", "company_name": "Infosys", "duration_minutes": 120, "total_questions": 40},
            {"title": "Aptitude Test", "duration_minutes": 60, "total_questions": 50},
            {"title": "Technical Interview Prep", "duration_minutes": 45, "total_questions": 30},
        ]
        
        for assessment_data in assessments_data:
            assessment = Assessment(**assessment_data)
            db.add(assessment)
        
        # Create some badges for the user
        badges = [
            Badge(user_id=user.id, title="Python Master", description="Completed all Python challenges", is_super_badge=False),
            Badge(user_id=user.id, title="DSA Champion", description="Solved 500+ problems", is_super_badge=True),
            Badge(user_id=user.id, title="Fast Coder", description="Completed test in record time", is_super_badge=False),
        ]
        for badge in badges:
            db.add(badge)
        
        await db.commit()
        print("✅ Database seeded successfully!")
        print(f"   Admin user: admin@autonex.ai / admin123")
        print(f"   Demo user: {user.email} / password123")


if __name__ == "__main__":
    asyncio.run(seed_database())

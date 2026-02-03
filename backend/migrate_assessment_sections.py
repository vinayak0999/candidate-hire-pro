"""
Migration script for Assessment Management feature.
Adds:
- test_sections table
- assessment_type, category columns to tests table
- section_id, question_number, passage_id columns to questions table
"""
import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


async def migrate():
    """Run migration to add assessment structures."""
    
    async with engine.begin() as conn:
        print("🚀 Starting Assessment Management migration...")
        
        # 1. Create test_sections table
        print("📦 Creating test_sections table...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS test_sections (
                id SERIAL PRIMARY KEY,
                test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                instructions TEXT,
                total_marks FLOAT DEFAULT 0,
                "order" INTEGER DEFAULT 0,
                passage TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        
        # Create index on test_id
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_test_sections_test_id 
            ON test_sections(test_id)
        """))
        
        # 2. Add new columns to tests table
        print("📝 Adding assessment_type and category to tests table...")
        
        # Check if columns exist before adding
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tests' AND column_name = 'assessment_type'
        """))
        if not result.fetchone():
            await conn.execute(text("""
                ALTER TABLE tests 
                ADD COLUMN assessment_type VARCHAR(20) DEFAULT 'job_test'
            """))
        
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tests' AND column_name = 'category'
        """))
        if not result.fetchone():
            await conn.execute(text("""
                ALTER TABLE tests 
                ADD COLUMN category VARCHAR(100)
            """))
        
        # 3. Add new columns to questions table
        print("📝 Adding section_id, question_number, passage_id to questions table...")
        
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'questions' AND column_name = 'section_id'
        """))
        if not result.fetchone():
            await conn.execute(text("""
                ALTER TABLE questions 
                ADD COLUMN section_id INTEGER REFERENCES test_sections(id) ON DELETE SET NULL
            """))
        
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'questions' AND column_name = 'question_number'
        """))
        if not result.fetchone():
            await conn.execute(text("""
                ALTER TABLE questions 
                ADD COLUMN question_number VARCHAR(20)
            """))
        
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'questions' AND column_name = 'passage_id'
        """))
        if not result.fetchone():
            await conn.execute(text("""
                ALTER TABLE questions 
                ADD COLUMN passage_id VARCHAR(50)
            """))
        
        # Create index for section_id
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_questions_section_id 
            ON questions(section_id)
        """))
        
        print("✅ Migration completed successfully!")
        print("")
        print("Summary of changes:")
        print("  - Created test_sections table")
        print("  - Added tests.assessment_type (default: 'job_test')")
        print("  - Added tests.category")
        print("  - Added questions.section_id")
        print("  - Added questions.question_number")
        print("  - Added questions.passage_id")


async def rollback():
    """Rollback migration (for development only)."""
    
    async with engine.begin() as conn:
        print("⚠️  Rolling back Assessment Management migration...")
        
        # Drop columns from questions first (due to FK)
        await conn.execute(text("ALTER TABLE questions DROP COLUMN IF EXISTS section_id"))
        await conn.execute(text("ALTER TABLE questions DROP COLUMN IF EXISTS question_number"))
        await conn.execute(text("ALTER TABLE questions DROP COLUMN IF EXISTS passage_id"))
        
        # Drop test_sections table
        await conn.execute(text("DROP TABLE IF EXISTS test_sections CASCADE"))
        
        # Drop columns from tests
        await conn.execute(text("ALTER TABLE tests DROP COLUMN IF EXISTS assessment_type"))
        await conn.execute(text("ALTER TABLE tests DROP COLUMN IF EXISTS category"))
        
        print("✅ Rollback completed!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())

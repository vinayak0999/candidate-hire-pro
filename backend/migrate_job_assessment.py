"""
Migration script to update job and test tables for assessment integration
Run with: python migrate_job_assessment.py
"""
import asyncio
from sqlalchemy import text
from app.database import engine

async def migrate():
    async with engine.begin() as conn:
        print("🔄 Starting migration for Job Assessment Integration...")

        # 1. Add test_id to jobs table
        try:
            await conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS test_id INTEGER NULL REFERENCES tests(id);
            """))
            print("✅ Added test_id to jobs table")
        except Exception as e:
            print(f"⚠️ Error adding test_id to jobs: {e}")

        # 2. Add anti-cheat columns to tests table
        try:
            await conn.execute(text("""
                ALTER TABLE tests 
                ADD COLUMN IF NOT EXISTS enable_tab_switch_detection BOOLEAN DEFAULT TRUE,
                ADD COLUMN IF NOT EXISTS max_tab_switches_allowed INTEGER DEFAULT 3;
            """))
            print("✅ Added anti-cheat columns to tests table")
        except Exception as e:
            print(f"⚠️ Error adding columns to tests: {e}")

        # 3. Add Indexes for performance
        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_test_attempts_user_test 
                ON test_attempts(user_id, test_id, status);
            """))
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_job_applications_user_job 
                ON job_applications(user_id, job_id);
            """))
            print("✅ Added performance indexes")
        except Exception as e:
            print(f"⚠️ Error adding indexes: {e}")
            
        print("🎉 Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())

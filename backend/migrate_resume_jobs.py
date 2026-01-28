"""
Migration: Add resume_parsing_jobs table for background processing.

Run this script to create the resume_parsing_jobs table.
"""
import asyncio
from sqlalchemy import text
from app.database import engine


async def migrate():
    """Create the resume_parsing_jobs table."""
    
    # Execute each statement separately (asyncpg requirement)
    statements = [
        """
        CREATE TABLE IF NOT EXISTS resume_parsing_jobs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            resume_filename VARCHAR(255) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_resume_jobs_user_id ON resume_parsing_jobs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_resume_jobs_status ON resume_parsing_jobs(status)"
    ]
    
    async with engine.begin() as conn:
        for sql in statements:
            await conn.execute(text(sql))
        print("✅ Created resume_parsing_jobs table and indexes")


if __name__ == "__main__":
    print("Running migration: Add resume_parsing_jobs table...")
    asyncio.run(migrate())
    print("Migration complete!")

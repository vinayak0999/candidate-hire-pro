"""
Migration script to add Agent Analysis columns to the database.
- tests.agent_analysis_count - count of agent analysis questions in a test
- questions.html_content - HTML file URL for agent analysis questions
- questions.documents - JSON array of document references
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.database import engine


async def migrate():
    """Add agent analysis columns to tests and questions tables."""
    print("Starting Agent Analysis migration...")
    
    async with engine.begin() as conn:
        # Check if agent_analysis_count column exists in tests table
        try:
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'tests' AND column_name = 'agent_analysis_count'"
            ))
            exists = result.fetchone() is not None
            
            if not exists:
                print("Adding agent_analysis_count column to tests table...")
                await conn.execute(text(
                    "ALTER TABLE tests ADD COLUMN agent_analysis_count INTEGER DEFAULT 0"
                ))
                print("✓ Added agent_analysis_count to tests table")
            else:
                print("✓ agent_analysis_count column already exists in tests table")
        except Exception as e:
            print(f"Error adding agent_analysis_count: {e}")
        
        # Check if html_content column exists in questions table
        try:
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'questions' AND column_name = 'html_content'"
            ))
            exists = result.fetchone() is not None
            
            if not exists:
                print("Adding html_content column to questions table...")
                await conn.execute(text(
                    "ALTER TABLE questions ADD COLUMN html_content TEXT"
                ))
                print("✓ Added html_content to questions table")
            else:
                print("✓ html_content column already exists in questions table")
        except Exception as e:
            print(f"Error adding html_content: {e}")
        
        # Check if documents column exists in questions table
        try:
            result = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'questions' AND column_name = 'documents'"
            ))
            exists = result.fetchone() is not None
            
            if not exists:
                print("Adding documents column to questions table...")
                await conn.execute(text(
                    "ALTER TABLE questions ADD COLUMN documents JSONB"
                ))
                print("✓ Added documents to questions table")
            else:
                print("✓ documents column already exists in questions table")
        except Exception as e:
            print(f"Error adding documents: {e}")
    
    print("\n✅ Agent Analysis migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())

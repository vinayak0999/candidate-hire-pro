"""
Migration script to add wizard fields to candidate_profiles table.
Run with: python migrate_wizard_fields.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

async def migrate():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in .env")
        return
    
    engine = create_async_engine(database_url)
    
    async with engine.begin() as conn:
        # Add has_data_annotation_experience column
        try:
            await conn.execute(text("""
                ALTER TABLE candidate_profiles 
                ADD COLUMN IF NOT EXISTS has_data_annotation_experience BOOLEAN
            """))
            print("✅ Added has_data_annotation_experience column")
        except Exception as e:
            print(f"⚠️ has_data_annotation_experience: {e}")
        
        # Add why_annotation column
        try:
            await conn.execute(text("""
                ALTER TABLE candidate_profiles 
                ADD COLUMN IF NOT EXISTS why_annotation TEXT
            """))
            print("✅ Added why_annotation column")
        except Exception as e:
            print(f"⚠️ why_annotation: {e}")
    
    await engine.dispose()
    print("\n🎉 Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())

"""
Script to delete all test attempts and answers
Run with: python clear_test_results.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

async def clear_all_test_results():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in .env")
        return
    
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Delete user answers first (FK constraint)
        await session.execute(text("DELETE FROM user_answers"))
        print("✅ Deleted all user answers")
        
        # Delete test attempts
        await session.execute(text("DELETE FROM test_attempts"))
        print("✅ Deleted all test attempts")
        
        await session.commit()
        
        # Verify
        result = await session.execute(text("SELECT COUNT(*) FROM test_attempts"))
        count = result.scalar()
        print(f"📊 Remaining test attempts: {count}")
        
    await engine.dispose()
    print("\n🎉 All test results cleared! Users can now take tests again.")

if __name__ == "__main__":
    asyncio.run(clear_all_test_results())

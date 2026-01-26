"""
Migration script to create notification tables
Run with: python migrate_notifications.py
"""
import asyncio
from sqlalchemy import text
from app.database import engine

async def migrate():
    async with engine.begin() as conn:
        # Create NotificationType enum
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE notificationtype AS ENUM ('announcement', 'info', 'alert', 'system');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Create TargetAudience enum
        await conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE targetaudience AS ENUM ('all', 'batch', 'branch');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        
        # Create notifications table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                notification_type notificationtype DEFAULT 'announcement',
                target_audience targetaudience DEFAULT 'all',
                target_value VARCHAR(100),
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ,
                is_active BOOLEAN DEFAULT TRUE
            );
        """))
        
        # Create user_notifications table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                notification_id INTEGER NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
                is_read BOOLEAN DEFAULT FALSE,
                read_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(user_id, notification_id)
            );
        """))
        
        # Create indexes (each in a separate statement for asyncpg compatibility)
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_notifications_active ON notifications(is_active);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at DESC);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_notifications_user ON user_notifications(user_id);
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_user_notifications_unread ON user_notifications(user_id, is_read);
        """))
        
        print("✅ Notification tables created successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())

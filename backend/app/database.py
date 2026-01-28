from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .config import get_settings

settings = get_settings()

# Configure connection arguments based on database type
# Supabase/PostgreSQL with PgBouncer needs statement_cache_size=0
# SQLite doesn't support these parameters
connect_args = {}
if "postgresql" in settings.database_url:
    connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

engine = create_async_engine(
    settings.database_url, 
    echo=settings.debug,
    connect_args=connect_args,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=300,    # Recycle connections every 5 minutes
    pool_size=20,        # Base pool size for concurrent connections
    max_overflow=30,     # Allow up to 50 total connections per worker
)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

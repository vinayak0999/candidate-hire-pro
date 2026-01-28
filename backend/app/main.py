from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .config import get_settings
from .database import init_db
from .routers import auth_router, jobs_router, courses_router, assessments_router, admin_router, tests_router, profile_router, notification_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title=settings.app_name,
    description="Autonex Assessment Portal API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware - uses origins from environment variable
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(courses_router)
app.include_router(assessments_router)
app.include_router(admin_router)
app.include_router(tests_router)
app.include_router(profile_router)
app.include_router(notification_router)

# Mount uploads directory for serving files
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


@app.get("/")
async def root():
    return {"message": "CDC Assessment Portal API", "status": "running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer"""
    return {"status": "healthy"}

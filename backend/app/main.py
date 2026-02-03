from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .config import get_settings
from .database import init_db
from .routers import auth_router, jobs_router, courses_router, assessments_router, admin_router, tests_router, profile_router, notification_router, standalone_assessments_router

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
    expose_headers=["*"],
)


# Cache control middleware - prevents browser caching of API responses
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Add no-cache headers to API responses (not static files)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

# Include routers
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(courses_router)
app.include_router(assessments_router)
app.include_router(admin_router)
app.include_router(tests_router)
app.include_router(profile_router)
app.include_router(notification_router)
app.include_router(standalone_assessments_router)

# Setup uploads directory path
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(uploads_dir, exist_ok=True)


# Video fallback route - MUST be before StaticFiles mount to take precedence
@app.get("/uploads/video_{video_id}.mp4")
async def fallback_video(video_id: str):
    """Fallback: redirect to Cloudinary if video not in local uploads"""
    from fastapi.responses import RedirectResponse, FileResponse
    
    # Try local first
    local_path = os.path.join(uploads_dir, f"video_{video_id}.mp4")
    if os.path.exists(local_path):
        return FileResponse(local_path, media_type="video/mp4")
    
    # Redirect to Cloudinary
    cloudinary_url = f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}/video/upload/hiring-pro/test-videos/video_{video_id}.mp4"
    return RedirectResponse(url=cloudinary_url, status_code=302)


# Mount uploads directory for other static files (comes after route so route takes precedence)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Mount static directory for large documents (>10MB that exceed cloud limits)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return {"message": "CDC Assessment Portal API", "status": "running", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer"""
    return {"status": "healthy"}

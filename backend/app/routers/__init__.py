from .auth import router as auth_router
from .jobs import router as jobs_router
from .courses import router as courses_router
from .assessments import router as assessments_router
from .admin import router as admin_router
from .tests import router as tests_router
from .profile import router as profile_router
from .notification import router as notification_router

__all__ = [
    "auth_router", "jobs_router", "courses_router", "assessments_router",
    "admin_router", "tests_router", "profile_router", "notification_router"
]

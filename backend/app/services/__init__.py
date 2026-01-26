from .auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    authenticate_user,
    oauth2_scheme
)
from .email import (
    generate_otp,
    generate_reset_token,
    get_otp_expiry,
    get_reset_token_expiry,
    send_otp_email,
    send_welcome_email,
    send_password_reset_email
)
from .resume_parser import (
    ParsedResume,
    parse_resume_with_gemini,
    normalize_skill_name,
    deduplicate_skills
)
from .vector_search import (
    vector_search_service,
    extract_skills_from_query
)
from .cloudinary_service import (
    upload_video,
    upload_image,
    upload_document,
    delete_media,
    upload_test_proctoring_video,
    upload_test_screenshot,
    is_cloudinary_available
)

__all__ = [
    # Auth
    "verify_password",
    "get_password_hash", 
    "create_access_token",
    "get_current_user",
    "authenticate_user",
    "oauth2_scheme",
    # Email
    "generate_otp",
    "generate_reset_token",
    "get_otp_expiry",
    "get_reset_token_expiry",
    "send_otp_email",
    "send_welcome_email",
    "send_password_reset_email",
    # Resume parsing
    "ParsedResume",
    "parse_resume_with_gemini",
    "normalize_skill_name",
    "deduplicate_skills",
    # Vector search
    "vector_search_service",
    "extract_skills_from_query",
    # Cloudinary
    "upload_video",
    "upload_image",
    "upload_document",
    "delete_media",
    "upload_test_proctoring_video",
    "upload_test_screenshot",
    "is_cloudinary_available"
]

from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    app_name: str = "CDC Assessment Portal API"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Database - supports both SQLite (local) and PostgreSQL (production)
    database_url: str = "sqlite+aiosqlite:///./cdc_portal.db"
    
    # Security - MUST be set via environment variables in production
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    
    # CORS - comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5173"
    
    # AWS (optional)
    aws_region: str = "ap-south-1"
    s3_bucket: str = ""
    
    # Email Configuration
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@autonex.ai"
    mail_from_name: str = "Autonex AI"
    mail_port: int = 587
    mail_server: str = "smtp.gmail.com"
    mail_starttls: bool = True
    mail_ssl_tls: bool = False
    mail_validate_certs: bool = True  # Set to False locally if SSL cert issues
    
    # Frontend URL for email links
    frontend_url: str = "http://localhost:5173"
    
    # OTP Settings
    otp_expire_minutes: int = 10
    reset_token_expire_minutes: int = 60
    
    # AI/LLM Configuration
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    
    # Vector Search (Pinecone)
    pinecone_api_key: str = ""
    pinecone_index_name: str = "candidate-profiles"
    pinecone_environment: str = "us-east-1"
    
    # Cloudinary (media storage)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"
        # Make field names case-insensitive for environment variables
        case_sensitive = False
    
    def get_cors_origins(self) -> list:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()

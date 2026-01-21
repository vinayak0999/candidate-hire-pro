from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    app_name: str = "CDC Assessment Portal API"
    debug: bool = False
    
    # Database - supports both SQLite (local) and PostgreSQL (production)
    database_url: str = "sqlite+aiosqlite:///./cdc_portal.db"
    
    # Security - MUST be set via environment variables in production
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    
    # CORS - comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:5174"
    
    # AWS (optional)
    aws_region: str = "ap-south-1"
    s3_bucket: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"
    
    def get_cors_origins(self) -> list:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from ..models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    name: str
    registration_number: str


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfile(UserBase):
    id: int
    degree: Optional[str] = None
    branch: Optional[str] = None
    batch: Optional[str] = None
    college: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: UserRole
    is_verified: bool = False
    neo_pat_score: int
    solved_easy: int
    solved_medium: int
    solved_hard: int
    badges_count: int
    super_badges_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from ..models.job import JobStatus, OfferType


class JobBase(BaseModel):
    company_name: str
    role: str
    location: Optional[str] = None
    ctc: Optional[float] = None
    job_type: str = "Full Time"
    offer_type: OfferType = OfferType.REGULAR


class JobCreate(JobBase):
    company_logo: Optional[str] = None
    round_date: Optional[datetime] = None
    test_id: Optional[int] = None


class JobResponse(JobBase):
    id: int
    company_logo: Optional[str] = None
    round_date: Optional[datetime] = None
    test_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    application_status: Optional[JobStatus] = None
    test_completed: Optional[bool] = False

    class Config:
        from_attributes = True


class JobApplicationResponse(BaseModel):
    id: int
    job_id: int
    status: JobStatus
    applied_at: datetime
    job: JobResponse

    class Config:
        from_attributes = True


class JobStats(BaseModel):
    total_jobs: int
    placed: int
    waiting: int
    rejected: int

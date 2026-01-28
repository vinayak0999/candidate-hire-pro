from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models.user import User
from ..models.job import Job, JobApplication, JobStatus
from ..schemas.job import JobResponse, JobApplicationResponse, JobStats
from ..services.auth import get_current_user

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.get("", response_model=list[JobResponse])
async def get_all_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all available jobs"""
    result = await db.execute(
        select(Job).where(Job.is_active == True).order_by(Job.created_at.desc())
    )
    jobs = result.scalars().all()
    
    # Get user's applications
    app_result = await db.execute(
        select(JobApplication).where(JobApplication.user_id == current_user.id)
    )
    applications = {app.job_id: app.status for app in app_result.scalars().all()}
    
    # Add application status to jobs
    job_responses = []
    for job in jobs:
        job_dict = {
            "id": job.id,
            "company_name": job.company_name,
            "company_logo": job.company_logo,
            "role": job.role,
            "location": job.location,
            "ctc": job.ctc,
            "job_type": job.job_type,
            "offer_type": job.offer_type,
            "round_date": job.round_date,
            "test_id": job.test_id,
            "is_active": job.is_active,
            "created_at": job.created_at,
            "application_status": applications.get(job.id)
        }
        job_responses.append(JobResponse(**job_dict))
    
    return job_responses


@router.get("/my", response_model=list[JobResponse])
async def get_my_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get jobs user has applied to"""
    result = await db.execute(
        select(Job, JobApplication)
        .join(JobApplication, Job.id == JobApplication.job_id)
        .where(JobApplication.user_id == current_user.id)
        .order_by(JobApplication.applied_at.desc())
    )
    rows = result.all()
    
    job_responses = []
    for job, application in rows:
        job_dict = {
            "id": job.id,
            "company_name": job.company_name,
            "company_logo": job.company_logo,
            "role": job.role,
            "location": job.location,
            "ctc": job.ctc,
            "job_type": job.job_type,
            "offer_type": job.offer_type,
            "round_date": job.round_date,
            "test_id": job.test_id,
            "is_active": job.is_active,
            "created_at": job.created_at,
            "application_status": application.status
        }
        job_responses.append(JobResponse(**job_dict))
    
    return job_responses


@router.post("/{job_id}/apply", response_model=JobResponse)
async def apply_to_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Apply to a job"""
    # Check job exists
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check not already applied
    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.user_id == current_user.id)
        .where(JobApplication.job_id == job_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already applied to this job")
    
    # Create application
    application = JobApplication(user_id=current_user.id, job_id=job_id)
    db.add(application)
    await db.commit()
    
    return JobResponse(
        id=job.id,
        company_name=job.company_name,
        company_logo=job.company_logo,
        role=job.role,
        location=job.location,
        ctc=job.ctc,
        job_type=job.job_type,
        offer_type=job.offer_type,
        round_date=job.round_date,
        test_id=job.test_id,
        is_active=job.is_active,
        created_at=job.created_at,
        application_status=JobStatus.APPLIED
    )


@router.post("/{job_id}/start-assessment")
async def start_assessment(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start assessment for a job"""
    # Check job exists
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job or not job.test_id:
        raise HTTPException(status_code=404, detail="Assessment not found for this job")
        
    # Check if applied
    app_result = await db.execute(
        select(JobApplication)
        .where(JobApplication.user_id == current_user.id)
        .where(JobApplication.job_id == job_id)
    )
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Must apply to job first")
        
    return {"test_id": job.test_id}


@router.get("/stats", response_model=JobStats)
async def get_job_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get job statistics for current user"""
    # Total jobs
    total_result = await db.execute(select(func.count(Job.id)).where(Job.is_active == True))
    total_jobs = total_result.scalar() or 0
    
    # User's applications by status
    apps_result = await db.execute(
        select(JobApplication.status, func.count(JobApplication.id))
        .where(JobApplication.user_id == current_user.id)
        .group_by(JobApplication.status)
    )
    status_counts = {row[0]: row[1] for row in apps_result.all()}
    
    return JobStats(
        total_jobs=total_jobs,
        placed=status_counts.get(JobStatus.SELECTED, 0),
        waiting=status_counts.get(JobStatus.APPLIED, 0) + status_counts.get(JobStatus.SHORTLISTED, 0),
        rejected=status_counts.get(JobStatus.REJECTED, 0)
    )

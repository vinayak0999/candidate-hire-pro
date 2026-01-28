"""
Supabase Storage Upload Service

Properly handles file uploads to Supabase Storage with Content-Length header.
"""
import os
from dotenv import load_dotenv
load_dotenv()  # Load .env file

import httpx
from io import BytesIO
from fastapi import UploadFile, HTTPException


async def upload_to_supabase(
    file: UploadFile,
    bucket: str,
    file_path: str,
    content_type: str = None
) -> str:
    """
    Upload a file to Supabase Storage with proper Content-Length header.
    
    Args:
        file: FastAPI UploadFile object
        bucket: Supabase storage bucket name
        file_path: Path within the bucket (e.g., "html/abc123_file.html")
        content_type: Optional content type override
    
    Returns:
        Public URL of the uploaded file
    
    Raises:
        HTTPException on upload failure
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase configuration missing")
    
    # Read entire file into memory (we need Content-Length)
    try:
        content = await file.read()
        file_size = len(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
    
    # Check file size limit (100MB)
    if file_size > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 100MB)")
    
    # Determine content type
    if content_type is None:
        content_type = file.content_type or "application/octet-stream"
    
    # Upload with explicit Content-Length
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{supabase_url}/storage/v1/object/{bucket}/{file_path}",
                headers={
                    "Authorization": f"Bearer {supabase_key}",
                    "apikey": supabase_key,
                    "Content-Type": content_type,
                    "Content-Length": str(file_size),
                },
                content=content
            )
            
            if response.status_code in [200, 201]:
                public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{file_path}"
                return public_url
            else:
                error_detail = response.text[:500] if response.text else "Unknown error"
                raise HTTPException(
                    status_code=500, 
                    detail=f"Supabase upload failed ({response.status_code}): {error_detail}"
                )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upload timeout - file too large or slow connection")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


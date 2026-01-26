"""
Cloudinary Service - Upload and manage test-related media (videos, images, documents)
"""
import cloudinary
import cloudinary.uploader
import cloudinary.api
from typing import Optional, Dict, Any, BinaryIO
import logging

logger = logging.getLogger(__name__)

# Initialize Cloudinary from settings
def init_cloudinary():
    """Initialize Cloudinary SDK from app settings"""
    from ..config import get_settings
    settings = get_settings()
    
    cloud_name = settings.cloudinary_cloud_name
    api_key = settings.cloudinary_api_key
    api_secret = settings.cloudinary_api_secret
    
    if not all([cloud_name, api_key, api_secret]):
        logger.warning("Cloudinary credentials not configured. Media uploads will fail.")
        return False
    
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )
    logger.info(f"✅ Cloudinary initialized: {cloud_name}")
    return True


# Check if Cloudinary is available
_cloudinary_available = init_cloudinary()


def is_cloudinary_available() -> bool:
    """Check if Cloudinary is properly configured"""
    return _cloudinary_available


async def upload_video(
    file: BinaryIO,
    folder: str = "hiring-pro/test-videos",
    public_id: Optional[str] = None,
    resource_type: str = "video"
) -> Optional[Dict[str, Any]]:
    """
    Upload a video file to Cloudinary
    
    Args:
        file: File-like object or file path
        folder: Cloudinary folder path
        public_id: Optional custom public ID
        resource_type: 'video' for video files
    
    Returns:
        Dict with url, public_id, etc. or None on failure
    """
    if not _cloudinary_available:
        logger.error("Cloudinary not configured")
        return None
    
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            public_id=public_id,
            resource_type=resource_type,
            # Video-specific options
            eager=[
                {"format": "mp4", "video_codec": "h264"},  # Optimized version
            ],
            eager_async=True
        )
        
        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id"),
            "format": result.get("format"),
            "duration": result.get("duration"),
            "bytes": result.get("bytes"),
            "width": result.get("width"),
            "height": result.get("height"),
        }
    except Exception as e:
        logger.error(f"Failed to upload video: {e}")
        return None


async def upload_image(
    file: BinaryIO,
    folder: str = "hiring-pro/test-screenshots",
    public_id: Optional[str] = None,
    transformation: Optional[Dict] = None
) -> Optional[Dict[str, Any]]:
    """
    Upload an image file to Cloudinary
    
    Args:
        file: File-like object or file path
        folder: Cloudinary folder path
        public_id: Optional custom public ID
        transformation: Optional image transformation
    
    Returns:
        Dict with url, public_id, etc. or None on failure
    """
    if not _cloudinary_available:
        logger.error("Cloudinary not configured")
        return None
    
    try:
        upload_options = {
            "folder": folder,
            "resource_type": "image",
        }
        
        if public_id:
            upload_options["public_id"] = public_id
            
        if transformation:
            upload_options["transformation"] = transformation
        
        result = cloudinary.uploader.upload(file, **upload_options)
        
        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id"),
            "format": result.get("format"),
            "bytes": result.get("bytes"),
            "width": result.get("width"),
            "height": result.get("height"),
        }
    except Exception as e:
        logger.error(f"Failed to upload image: {e}")
        return None


async def upload_document(
    file: BinaryIO,
    folder: str = "hiring-pro/test-documents",
    public_id: Optional[str] = None,
    filename: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Upload a document (PDF, etc.) to Cloudinary
    
    Args:
        file: File-like object or file path
        folder: Cloudinary folder path
        public_id: Optional custom public ID
        filename: Original filename for display
    
    Returns:
        Dict with url, public_id, etc. or None on failure
    """
    if not _cloudinary_available:
        logger.error("Cloudinary not configured")
        return None
    
    try:
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            public_id=public_id,
            resource_type="raw",  # For non-image/video files
        )
        
        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id"),
            "format": result.get("format"),
            "bytes": result.get("bytes"),
            "filename": filename,
        }
    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        return None


async def delete_media(public_id: str, resource_type: str = "image") -> bool:
    """
    Delete media from Cloudinary
    
    Args:
        public_id: The public ID of the media to delete
        resource_type: 'image', 'video', or 'raw'
    
    Returns:
        True if deleted successfully
    """
    if not _cloudinary_available:
        return False
    
    try:
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type=resource_type
        )
        return result.get("result") == "ok"
    except Exception as e:
        logger.error(f"Failed to delete media: {e}")
        return False


def get_optimized_url(
    public_id: str,
    resource_type: str = "image",
    transformation: Optional[Dict] = None
) -> str:
    """
    Get an optimized URL for a media file
    
    Args:
        public_id: The public ID of the media
        resource_type: 'image' or 'video'
        transformation: Optional transformation parameters
    
    Returns:
        Optimized URL
    """
    default_transformations = {
        "image": {"quality": "auto", "fetch_format": "auto"},
        "video": {"quality": "auto"},
    }
    
    trans = transformation or default_transformations.get(resource_type, {})
    
    return cloudinary.CloudinaryImage(public_id).build_url(
        resource_type=resource_type,
        **trans
    )


async def upload_test_proctoring_video(
    file: BinaryIO,
    test_attempt_id: int,
    user_id: int
) -> Optional[Dict[str, Any]]:
    """
    Upload a proctoring video for a specific test attempt
    
    Args:
        file: Video file
        test_attempt_id: The test attempt ID
        user_id: The user ID
    
    Returns:
        Upload result dict
    """
    folder = f"hiring-pro/proctoring/{user_id}"
    public_id = f"test_attempt_{test_attempt_id}"
    
    return await upload_video(file, folder=folder, public_id=public_id)


async def upload_test_screenshot(
    file: BinaryIO,
    test_attempt_id: int,
    user_id: int,
    screenshot_number: int
) -> Optional[Dict[str, Any]]:
    """
    Upload a screenshot from test proctoring
    
    Args:
        file: Image file
        test_attempt_id: The test attempt ID
        user_id: The user ID
        screenshot_number: Sequential screenshot number
    
    Returns:
        Upload result dict
    """
    folder = f"hiring-pro/proctoring/{user_id}/screenshots"
    public_id = f"test_{test_attempt_id}_screenshot_{screenshot_number}"
    
    return await upload_image(file, folder=folder, public_id=public_id)

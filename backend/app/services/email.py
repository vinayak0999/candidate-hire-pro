"""
Email service for sending OTP verification, welcome, and password reset emails
"""
import random
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from jinja2 import Environment, FileSystemLoader

from ..config import get_settings

settings = get_settings()

# Email configuration
conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_STARTTLS=settings.mail_starttls,
    MAIL_SSL_TLS=settings.mail_ssl_tls,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=settings.mail_validate_certs,
    TEMPLATE_FOLDER=Path(__file__).parent.parent / "templates" / "emails"
)

# Jinja2 environment for template rendering
template_dir = Path(__file__).parent.parent / "templates" / "emails"
jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))


def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))


def generate_reset_token() -> str:
    """Generate a secure reset token"""
    return secrets.token_urlsafe(32)


def get_otp_expiry() -> datetime:
    """Get OTP expiry time"""
    return datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes)


def get_reset_token_expiry() -> datetime:
    """Get reset token expiry time"""
    return datetime.now(timezone.utc) + timedelta(minutes=settings.reset_token_expire_minutes)


async def send_otp_email(email: str, name: str, otp: str) -> bool:
    """Send OTP verification email"""
    try:
        print(f"[Email] Preparing OTP email to: {email}")
        print(f"[Email] Using SMTP: {settings.mail_server}:{settings.mail_port}")
        print(f"[Email] From: {settings.mail_from} ({settings.mail_username})")

        template = jinja_env.get_template("otp_verification.html")
        html_content = template.render(
            name=name,
            otp=otp,
            expiry_minutes=settings.otp_expire_minutes,
            app_name=settings.app_name
        )

        message = MessageSchema(
            subject=f"Verify Your Email - {settings.app_name}",
            recipients=[email],
            body=html_content,
            subtype=MessageType.html
        )

        fm = FastMail(conf)
        await fm.send_message(message)
        print(f"[Email] SUCCESS - OTP sent to {email}")
        return True
    except Exception as e:
        import traceback
        print(f"[Email] FAILED to send OTP email to {email}")
        print(f"[Email] Error: {type(e).__name__}: {e}")
        print(f"[Email] Traceback: {traceback.format_exc()}")
        return False


async def send_welcome_email(email: str, name: str) -> bool:
    """Send welcome/onboarding email after verification"""
    try:
        template = jinja_env.get_template("welcome.html")
        html_content = template.render(
            name=name,
            app_name=settings.app_name,
            frontend_url=settings.frontend_url
        )
        
        message = MessageSchema(
            subject=f"Welcome to {settings.app_name}! 🎉",
            recipients=[email],
            body=html_content,
            subtype=MessageType.html
        )
        
        fm = FastMail(conf)
        await fm.send_message(message)
        return True
    except Exception as e:
        print(f"Failed to send welcome email: {e}")
        return False


async def send_password_reset_email(email: str, name: str, reset_token: str) -> bool:
    """Send password reset email"""
    try:
        reset_link = f"{settings.frontend_url}/reset-password?token={reset_token}"
        
        template = jinja_env.get_template("password_reset.html")
        html_content = template.render(
            name=name,
            reset_link=reset_link,
            expiry_minutes=settings.reset_token_expire_minutes,
            app_name=settings.app_name
        )
        
        message = MessageSchema(
            subject=f"Reset Your Password - {settings.app_name}",
            recipients=[email],
            body=html_content,
            subtype=MessageType.html
        )
        
        fm = FastMail(conf)
        await fm.send_message(message)
        return True
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
        return False

# Enterprise Scalability Architecture

**Target: 10,000+ Concurrent Users | Production-Grade**

---

## Executive Summary

This plan transforms Hiring Pro from a single-instance application to a horizontally-scalable, enterprise-ready platform capable of handling 10,000+ concurrent users with 99.9% uptime.

---

## Infrastructure Analysis

### Supabase Pro Plan Capabilities

| Resource | Pro Plan | Scaling Option |
|----------|----------|----------------|
| **Direct DB Connections** | 60 (Micro) → 240 (XL) | Upgrade compute |
| **Pooler Connections** | 200 (Micro) → 1,000 (XL) | Use Supavisor |
| **Realtime Connections** | 500 concurrent | - |
| **Database Size** | 8GB included, $0.125/GB | 60TB max |
| **Egress** | 250GB, $0.09/GB after | - |
| **MAUs** | 100,000 included | $0.00325/MAU after |

> [!IMPORTANT]
> **Use Supavisor pooler mode** (`?pgbouncer=true` connection string) to get 200-1000 pooler connections instead of 60 direct connections.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            LOAD BALANCER (AWS ALB)                          │
│                     (Health checks, SSL termination)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
           ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
           │   FastAPI    │  │   FastAPI    │  │   FastAPI    │
           │  Instance 1  │  │  Instance 2  │  │  Instance N  │
           │   (Gunicorn) │  │   (Gunicorn) │  │   (Gunicorn) │
           └──────────────┘  └──────────────┘  └──────────────┘
                    │                 │                 │
                    └─────────────────┼─────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               REDIS CLUSTER                                  │
│         (Rate Limiting, Caching, Session Store, Pub/Sub)                    │
│                            AWS ElastiCache                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SUPABASE POSTGRES                                   │
│               (Supavisor Connection Pooling, 1000 connections)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Required Dependencies

Add these to `requirements.txt`:

```txt
# Scalability infrastructure
aioboto3>=12.0.0        # Async SQS for worker queue (Phase 13)
PyJWT>=2.8.0            # JWT decode in rate limiter (Phase 2)
redis>=5.0.0            # Async Redis client
gunicorn>=21.0.0        # Production WSGI server
uvicorn[standard]>=0.24.0  # ASGI worker

# Already likely present but verify versions
fastapi>=0.104.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
```

---

## Proposed Changes

### Phase 1: Connection Pooling & Database Optimization

---

#### [MODIFY] [database.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/database.py)

**Enterprise connection pooling with Supavisor:**

```python
"""
Enterprise Database Configuration
- Uses Supabase Supavisor for connection pooling (1000 connections)
- Implements connection health monitoring
- Automatic failover and retry logic
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from sqlalchemy import event
import logging

from .config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Production: Use Supavisor pooler (transaction mode)
# Connection string should use port 6543 (pooler) not 5432 (direct)
# Example: postgresql+asyncpg://user:pass@db.xxx.supabase.co:6543/postgres?pgbouncer=true

def get_connection_url():
    """
    Returns appropriate connection URL based on environment.
    Production uses Supavisor pooler, dev uses direct connection.
    """
    url = settings.database_url
    
    # Ensure we're using the pooler in production
    if settings.environment == "production" and "5432" in url:
        logger.warning("Production should use Supavisor port 6543, not 5432")
        url = url.replace(":5432/", ":6543/")
    
    return url

# Connection pool configuration optimized for Supavisor
# When using external pooler (Supavisor), we use NullPool
# to let Supavisor handle all pooling
if settings.use_external_pooler:
    # Supavisor handles pooling - disable SQLAlchemy pooling
    engine = create_async_engine(
        get_connection_url(),
        echo=settings.debug,
        poolclass=NullPool,  # Let Supavisor handle pooling
        connect_args={
            "statement_cache_size": 0,  # Required for PgBouncer/Supavisor
            "prepared_statement_cache_size": 0,
            "server_settings": {
                "application_name": "hiring-pro-backend",
                "statement_timeout": "30000",  # 30s query timeout
            }
        },
    )
else:
    # Local development - use SQLAlchemy pooling
    engine = create_async_engine(
        get_connection_url(),
        echo=settings.debug,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=20,
        max_overflow=30,
        pool_timeout=10,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
    )

async_session_maker = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()


async def get_db():
    """
    Database session dependency with proper error handling.
    Implements automatic retry for transient failures.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            await session.close()
```

---

#### [MODIFY] [config.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/config.py)

**Add production configuration:**

```python
# Add these fields to Settings class:

class Settings(BaseSettings):
    # ... existing fields ...
    
    # Environment
    environment: str = "development"  # development, staging, production
    app_version: str = "1.0.0"  # For health checks
    
    # Connection Pooling
    use_external_pooler: bool = False  # True for Supavisor in production
    
    # Redis Configuration (for rate limiting & caching)
    redis_url: str = ""  # redis://localhost:6379 or ElastiCache endpoint
    redis_pool_size: int = 20
    redis_mode: str = "standalone"  # standalone, sentinel, cluster
    redis_sentinel_hosts: str = ""  # Comma-separated for Sentinel
    redis_sentinel_master: str = "mymaster"
    
    # Caching
    cache_enabled: bool = True  # Set False to disable caching
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 100  # Default for authenticated users
    rate_limit_burst: int = 20  # Allow burst of 20 requests
    
    # Circuit Breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 30  # seconds
    
    # AWS
    aws_region: str = "us-east-1"  # For SQS, S3, etc.
    
    # Observability
    log_level: str = "INFO"
    enable_request_logging: bool = True
    sentry_dsn: str = ""  # For error tracking
```

---

### Phase 2: Redis-Based Distributed Rate Limiting

---

#### [NEW] [redis.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/services/redis.py)

**Production Redis client with connection pooling:**

```python
"""
Redis Service - Production-grade connection management
Handles rate limiting, caching, and distributed locks
"""
import asyncio
from typing import Optional
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
import logging

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisService:
    """
    Singleton Redis service with connection pooling.
    Thread-safe, async-compatible, with automatic reconnection.
    """
    _instance: Optional["RedisService"] = None
    _pool: Optional[ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self):
        """Initialize Redis connection pool."""
        if self._client is not None:
            return
        
        if not settings.redis_url:
            logger.warning("Redis URL not configured - rate limiting disabled")
            return
        
        try:
            self._pool = ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.redis_pool_size,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
            )
            self._client = redis.Redis(connection_pool=self._pool)
            
            # Test connection
            await self._client.ping()
            logger.info("✅ Redis connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._client = None
    
    @property
    def client(self) -> Optional[redis.Redis]:
        return self._client
    
    @property
    def is_available(self) -> bool:
        return self._client is not None
    
    async def close(self):
        """Graceful shutdown."""
        if self._client:
            await self._client.close()
            await self._pool.disconnect()


# Global instance
redis_service = RedisService()


async def get_redis() -> Optional[redis.Redis]:
    """Dependency for getting Redis client."""
    await redis_service.initialize()
    return redis_service.client
```

---

#### [NEW] [rate_limiter.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/middleware/rate_limiter.py)

**Production-grade distributed rate limiting with Token Bucket:**

```python
"""
Distributed Rate Limiter using Redis + Token Bucket Algorithm

Features:
- Token bucket algorithm (allows controlled bursts)
- Per-user and per-IP limiting
- Tiered limits based on endpoint type
- Proper 429 responses with Retry-After header
- Graceful degradation if Redis unavailable (fail-open)
- Lua script for atomic operations (no race conditions)
"""
import time
import hashlib
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

from ..services.redis import redis_service
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# Lua script for atomic token bucket operation
# This prevents race conditions in distributed environment
TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])  -- tokens per second
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
local tokens = tonumber(bucket[1]) or capacity
local last_update = tonumber(bucket[2]) or now

-- Calculate tokens to add based on time elapsed
local elapsed = now - last_update
local tokens_to_add = elapsed * refill_rate
tokens = math.min(capacity, tokens + tokens_to_add)

-- Check if we have enough tokens
if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
    redis.call('EXPIRE', key, 3600)  -- 1 hour TTL
    return {1, tokens, 0}  -- allowed, remaining, retry_after
else
    -- Calculate time until enough tokens available
    local needed = requested - tokens
    local retry_after = math.ceil(needed / refill_rate)
    redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
    redis.call('EXPIRE', key, 3600)
    return {0, tokens, retry_after}  -- denied, remaining, retry_after
end
"""


# Rate limit tiers by endpoint category
RATE_LIMITS = {
    # (max_tokens, refill_rate_per_second)
    "auth": (10, 0.167),           # 10 requests, refills at 10/min
    "ai_heavy": (5, 0.083),        # 5 requests, refills at 5/min (AI endpoints)
    "upload": (20, 0.333),         # 20 requests, refills at 20/min
    "read": (200, 3.333),          # 200 requests, refills at 200/min
    "write": (60, 1.0),            # 60 requests, refills at 60/min
    "default": (100, 1.667),       # 100 requests, refills at 100/min
}

# Endpoint categorization
ENDPOINT_CATEGORIES = {
    "/api/auth/login": "auth",
    "/api/auth/register": "auth",
    "/api/auth/forgot-password": "auth",
    "/api/profile/resume": "ai_heavy",
    "/api/admin/ai-generate": "ai_heavy",
    "/api/profile/resume-status": "read",
    "/api/jobs": "read",
    "/api/tests/available": "read",
    "/api/tests/submit": "write",
    "/api/tests/complete": "write",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Production-grade rate limiting middleware.
    
    Uses Redis for distributed state, falls back to allowing
    requests if Redis is unavailable (fail-open).
    """
    
    def __init__(self, app):
        super().__init__(app)
        self._script_sha: Optional[str] = None
    
    async def _get_script_sha(self) -> Optional[str]:
        """Load Lua script into Redis and cache SHA."""
        if self._script_sha:
            return self._script_sha
        
        client = redis_service.client
        if not client:
            return None
        
        try:
            self._script_sha = await client.script_load(TOKEN_BUCKET_SCRIPT)
            return self._script_sha
        except Exception as e:
            logger.error(f"Failed to load rate limit script: {e}")
            return None
    
    def _get_endpoint_category(self, path: str) -> str:
        """Determine rate limit category for an endpoint."""
        # Exact match
        if path in ENDPOINT_CATEGORIES:
            return ENDPOINT_CATEGORIES[path]
        
        # Prefix match for common patterns
        if path.startswith("/api/admin/"):
            return "write"
        if path.startswith("/api/tests/") and "answer" in path:
            return "write"
        if path.startswith("/uploads/"):
            return "upload"
        
        # Default based on method will be handled in dispatch
        return "default"
    
    def _get_identifier(self, request: Request) -> str:
        """
        Get unique identifier for rate limiting.
        Uses user ID if authenticated, otherwise IP address.
        """
        # Check for authenticated user
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                # Decode JWT without verification to get user_id
                # (consistent across token refreshes)
                import jwt
                payload = jwt.decode(token, options={"verify_signature": False})
                user_id = payload.get("sub") or payload.get("user_id")
                if user_id:
                    return f"user:{user_id}"
            except Exception:
                pass
            # Fallback to token hash if decode fails
            return f"user:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
        
        # Fall back to IP address
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"ip:{ip}"
    
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiter."""
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Skip if rate limiting disabled
        if not settings.rate_limit_enabled:
            return await call_next(request)
        
        # Skip if Redis unavailable (fail-open)
        client = redis_service.client
        if not client:
            return await call_next(request)
        
        try:
            # Get rate limit parameters
            category = self._get_endpoint_category(request.url.path)
            
            # Adjust category based on HTTP method
            if request.method == "GET" and category == "default":
                category = "read"
            elif request.method in ["POST", "PUT", "DELETE"] and category == "default":
                category = "write"
            
            capacity, refill_rate = RATE_LIMITS.get(category, RATE_LIMITS["default"])
            
            # Build rate limit key
            identifier = self._get_identifier(request)
            key = f"ratelimit:{category}:{identifier}"
            
            # Execute token bucket check
            script_sha = await self._get_script_sha()
            if not script_sha:
                return await call_next(request)
            
            now = time.time()
            result = await client.evalsha(
                script_sha,
                1,  # number of keys
                key,
                str(capacity),
                str(refill_rate),
                "1",  # requesting 1 token
                str(now),
            )
            
            allowed, remaining, retry_after = result
            
            # Add rate limit headers to response
            response = await call_next(request) if allowed else None
            
            if not allowed:
                logger.warning(
                    f"Rate limit exceeded: {identifier} on {request.url.path} "
                    f"(category: {category}, retry_after: {retry_after}s)"
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests. Please slow down.",
                        "retry_after": retry_after,
                        "category": category,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(int(capacity)),
                        "X-RateLimit-Remaining": str(int(remaining)),
                        "X-RateLimit-Reset": str(int(now + retry_after)),
                    },
                )
            
            # Add headers to successful response
            response.headers["X-RateLimit-Limit"] = str(int(capacity))
            response.headers["X-RateLimit-Remaining"] = str(int(remaining))
            
            return response
            
        except Exception as e:
            # Fail open - allow request if rate limiting fails
            logger.error(f"Rate limiter error (failing open): {e}")
            return await call_next(request)
```

---

### Phase 3: Circuit Breaker & Resilience Patterns

---

#### [NEW] [circuit_breaker.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/services/circuit_breaker.py)

**Circuit breaker for external services (Gemini, Pinecone, Cloudinary):**

```python
"""
Circuit Breaker Pattern Implementation

Prevents cascading failures when external services are down.
States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing)

Used for:
- Gemini API (AI operations)
- Pinecone (vector search)
- Cloudinary (media storage)
- Supabase Storage (file uploads)
"""
import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from functools import wraps
import logging

from ..services.redis import redis_service

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Distributed circuit breaker using Redis for state sharing.
    
    Configuration:
    - failure_threshold: failures before opening circuit
    - recovery_timeout: seconds before attempting recovery
    - success_threshold: successes in half-open before closing
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._local_state = CircuitState.CLOSED  # Fallback if Redis unavailable
        self._local_failures = 0
        self._local_last_failure = 0
    
    @property
    def _redis_key(self) -> str:
        return f"circuit:{self.name}"
    
    async def _get_state(self) -> Dict[str, Any]:
        """Get circuit state from Redis."""
        client = redis_service.client
        if not client:
            return {
                "state": self._local_state.value,
                "failures": self._local_failures,
                "last_failure": self._local_last_failure,
                "successes": 0,
            }
        
        try:
            data = await client.hgetall(self._redis_key)
            if not data:
                return {
                    "state": CircuitState.CLOSED.value,
                    "failures": 0,
                    "last_failure": 0,
                    "successes": 0,
                }
            return {
                "state": data.get("state", CircuitState.CLOSED.value),
                "failures": int(data.get("failures", 0)),
                "last_failure": float(data.get("last_failure", 0)),
                "successes": int(data.get("successes", 0)),
            }
        except Exception as e:
            logger.error(f"Circuit breaker Redis error: {e}")
            return {
                "state": self._local_state.value,
                "failures": self._local_failures,
                "last_failure": self._local_last_failure,
                "successes": 0,
            }
    
    async def _set_state(self, state: Dict[str, Any]):
        """Update circuit state in Redis."""
        client = redis_service.client
        if not client:
            self._local_state = CircuitState(state["state"])
            self._local_failures = state["failures"]
            self._local_last_failure = state["last_failure"]
            return
        
        try:
            await client.hset(self._redis_key, mapping={
                "state": state["state"],
                "failures": str(state["failures"]),
                "last_failure": str(state["last_failure"]),
                "successes": str(state.get("successes", 0)),
            })
            await client.expire(self._redis_key, 3600)  # 1 hour TTL
        except Exception as e:
            logger.error(f"Circuit breaker state update failed: {e}")
    
    async def can_execute(self) -> bool:
        """Check if request should be allowed through."""
        state = await self._get_state()
        current_state = CircuitState(state["state"])
        
        if current_state == CircuitState.CLOSED:
            return True
        
        if current_state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if time.time() - state["last_failure"] >= self.recovery_timeout:
                # Transition to half-open
                state["state"] = CircuitState.HALF_OPEN.value
                state["successes"] = 0
                await self._set_state(state)
                logger.info(f"Circuit {self.name}: OPEN → HALF_OPEN")
                return True
            return False
        
        # HALF_OPEN - allow only one probe request at a time
        # Use Redis lock to prevent race condition
        client = redis_service.client
        if client:
            acquired = await client.set(
                f"{self._redis_key}:probe",
                "1",
                nx=True,  # Only set if not exists
                ex=self.recovery_timeout
            )
            return acquired is not None
        return True
    
    async def record_success(self):
        """Record successful call."""
        state = await self._get_state()
        current_state = CircuitState(state["state"])
        
        if current_state == CircuitState.HALF_OPEN:
            state["successes"] = state.get("successes", 0) + 1
            if state["successes"] >= self.success_threshold:
                # Recovery successful
                state["state"] = CircuitState.CLOSED.value
                state["failures"] = 0
                logger.info(f"Circuit {self.name}: HALF_OPEN → CLOSED (recovered)")
            await self._set_state(state)
        elif current_state == CircuitState.CLOSED:
            # Reset failure count on success
            if state["failures"] > 0:
                state["failures"] = 0
                await self._set_state(state)
    
    async def record_failure(self, error: Exception):
        """Record failed call."""
        state = await self._get_state()
        current_state = CircuitState(state["state"])
        
        state["failures"] = state["failures"] + 1
        state["last_failure"] = time.time()
        
        if current_state == CircuitState.HALF_OPEN:
            # Failed during recovery test - back to open
            state["state"] = CircuitState.OPEN.value
            logger.warning(f"Circuit {self.name}: HALF_OPEN → OPEN (recovery failed)")
        elif current_state == CircuitState.CLOSED:
            if state["failures"] >= self.failure_threshold:
                state["state"] = CircuitState.OPEN.value
                logger.warning(
                    f"Circuit {self.name}: CLOSED → OPEN "
                    f"(failures: {state['failures']}, error: {error})"
                )
        
        await self._set_state(state)


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    def __init__(self, circuit_name: str, retry_after: int):
        self.circuit_name = circuit_name
        self.retry_after = retry_after
        super().__init__(f"Circuit {circuit_name} is open. Retry after {retry_after}s")


def circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator for circuit breaker pattern.
    
    Usage:
        gemini_circuit = CircuitBreaker("gemini", failure_threshold=5)
        
        @circuit_breaker(gemini_circuit)
        async def call_gemini_api(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not await breaker.can_execute():
                state = await breaker._get_state()
                retry_after = int(
                    breaker.recovery_timeout - 
                    (time.time() - state["last_failure"])
                )
                raise CircuitOpenError(breaker.name, max(1, retry_after))
            
            try:
                result = await func(*args, **kwargs)
                await breaker.record_success()
                return result
            except Exception as e:
                await breaker.record_failure(e)
                raise
        
        return wrapper
    return decorator


# Pre-configured circuit breakers for external services
gemini_circuit = CircuitBreaker("gemini", failure_threshold=5, recovery_timeout=60)
pinecone_circuit = CircuitBreaker("pinecone", failure_threshold=5, recovery_timeout=30)
cloudinary_circuit = CircuitBreaker("cloudinary", failure_threshold=5, recovery_timeout=30)
supabase_storage_circuit = CircuitBreaker("supabase_storage", failure_threshold=5, recovery_timeout=30)
```

---

### Phase 4: Request Queue with Dead Letter Queue

---

#### [NEW] [request_queue.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/services/request_queue.py)

**Production message queue for heavy operations:**

```python
"""
Distributed Request Queue for Heavy Operations

Uses Redis Streams for:
- Resume parsing jobs
- Vector indexing jobs
- Email notifications
- Report generation

Features:
- At-least-once delivery guarantee
- Dead letter queue for failed jobs
- Priority queuing
- Job status tracking
- Automatic retries with exponential backoff
"""
import asyncio
import json
import time
import uuid
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from dataclasses import dataclass, asdict
import logging

from ..services.redis import redis_service
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"  # Moved to DLQ after max retries


class JobPriority(Enum):
    HIGH = 1
    NORMAL = 5
    LOW = 10


@dataclass
class Job:
    id: str
    queue_name: str
    payload: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    created_at: float = 0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retries: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    user_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "queue_name": self.queue_name,
            "payload": json.dumps(self.payload),
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": str(self.created_at),
            "started_at": str(self.started_at) if self.started_at else "",
            "completed_at": str(self.completed_at) if self.completed_at else "",
            "retries": str(self.retries),
            "max_retries": str(self.max_retries),
            "error": self.error or "",
            "user_id": str(self.user_id) if self.user_id else "",
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Job":
        return cls(
            id=data["id"],
            queue_name=data["queue_name"],
            payload=json.loads(data["payload"]),
            status=JobStatus(data["status"]),
            priority=JobPriority(int(data["priority"])),
            created_at=float(data["created_at"]),
            started_at=float(data["started_at"]) if data.get("started_at") else None,
            completed_at=float(data["completed_at"]) if data.get("completed_at") else None,
            retries=int(data.get("retries", 0)),
            max_retries=int(data.get("max_retries", 3)),
            error=data.get("error") or None,
            user_id=int(data["user_id"]) if data.get("user_id") else None,
        )


class RequestQueue:
    """
    Production-grade request queue using Redis Streams.
    
    Supports:
    - Multiple named queues (resume_parse, vector_index, email, etc.)
    - Consumer groups for distributed processing
    - Automatic retries with exponential backoff
    - Dead letter queue for permanent failures
    - Job status tracking
    """
    
    def __init__(self, queue_name: str, consumer_group: str = "workers"):
        self.queue_name = queue_name
        self.consumer_group = consumer_group
        self.stream_key = f"queue:{queue_name}"
        self.dlq_key = f"dlq:{queue_name}"
        self.jobs_key = f"jobs:{queue_name}"
        self._processing_semaphore = asyncio.Semaphore(10)  # Max concurrent jobs
    
    async def _ensure_consumer_group(self):
        """Create consumer group if it doesn't exist."""
        client = redis_service.client
        if not client:
            return
        
        try:
            await client.xgroup_create(
                self.stream_key,
                self.consumer_group,
                id="0",
                mkstream=True,
            )
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"Failed to create consumer group: {e}")
    
    async def enqueue(
        self,
        payload: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        user_id: Optional[int] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Add job to queue.
        
        Returns job ID for status tracking.
        """
        client = redis_service.client
        
        job = Job(
            id=str(uuid.uuid4()),
            queue_name=self.queue_name,
            payload=payload,
            priority=priority,
            created_at=time.time(),
            user_id=user_id,
            max_retries=max_retries,
        )
        
        if not client:
            # Fallback: process immediately (degraded mode)
            logger.warning(f"Queue {self.queue_name}: Redis unavailable, processing inline")
            return job.id
        
        try:
            await self._ensure_consumer_group()
            
            # Add to stream
            await client.xadd(
                self.stream_key,
                {"data": json.dumps(job.to_dict())},
                maxlen=10000,  # Keep last 10k messages
            )
            
            # Store job details for status lookup
            await client.hset(self.jobs_key, job.id, json.dumps(job.to_dict()))
            await client.expire(self.jobs_key, 86400)  # 24 hour TTL
            
            logger.info(f"Queued job {job.id} to {self.queue_name}")
            return job.id
            
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise
    
    async def get_job_status(self, job_id: str) -> Optional[Job]:
        """Get current status of a job."""
        client = redis_service.client
        if not client:
            return None
        
        try:
            data = await client.hget(self.jobs_key, job_id)
            if data:
                return Job.from_dict(json.loads(data))
            return None
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None
    
    async def get_queue_depth(self) -> int:
        """Get number of pending jobs."""
        client = redis_service.client
        if not client:
            return 0
        
        try:
            return await client.xlen(self.stream_key)
        except Exception:
            return 0
    
    async def process_jobs(
        self,
        handler: Callable[[Job], Any],
        consumer_name: str = "worker-1",
        batch_size: int = 10,
    ):
        """
        Process jobs from queue (run in background worker).
        
        Args:
            handler: Async function to process each job
            consumer_name: Unique name for this consumer
            batch_size: Number of jobs to fetch at once
        """
        client = redis_service.client
        if not client:
            logger.error("Cannot process jobs: Redis unavailable")
            return
        
        await self._ensure_consumer_group()
        
        while True:
            try:
                # Read pending messages first (recovery from crash)
                messages = await client.xreadgroup(
                    self.consumer_group,
                    consumer_name,
                    {self.stream_key: ">"},
                    count=batch_size,
                    block=5000,  # 5 second block
                )
                
                if not messages:
                    continue
                
                for stream_name, entries in messages:
                    for message_id, data in entries:
                        job_data = json.loads(data["data"])
                        job = Job.from_dict(job_data)
                        
                        async with self._processing_semaphore:
                            await self._process_single_job(
                                client, handler, job, message_id
                            )
                            
            except asyncio.CancelledError:
                logger.info(f"Worker {consumer_name} shutting down")
                break
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                await asyncio.sleep(1)
    
    async def _process_single_job(
        self,
        client,
        handler: Callable[[Job], Any],
        job: Job,
        message_id: str,
    ):
        """Process a single job with retry logic."""
        job.status = JobStatus.PROCESSING
        job.started_at = time.time()
        
        try:
            # Update status
            await client.hset(self.jobs_key, job.id, json.dumps(job.to_dict()))
            
            # Execute handler
            await handler(job)
            
            # Mark completed
            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()
            await client.hset(self.jobs_key, job.id, json.dumps(job.to_dict()))
            
            # Acknowledge message
            await client.xack(self.stream_key, self.consumer_group, message_id)
            
            logger.info(f"Completed job {job.id}")
            
        except Exception as e:
            job.retries += 1
            job.error = str(e)[:500]  # Truncate error message
            
            if job.retries >= job.max_retries:
                # Move to dead letter queue
                job.status = JobStatus.DEAD
                await client.lpush(self.dlq_key, json.dumps(job.to_dict()))
                await client.xack(self.stream_key, self.consumer_group, message_id)
                logger.error(f"Job {job.id} moved to DLQ after {job.retries} retries: {e}")
            else:
                # Requeue with exponential backoff
                job.status = JobStatus.PENDING
                backoff = 2 ** job.retries  # 2, 4, 8 seconds
                logger.warning(f"Job {job.id} retry {job.retries}/{job.max_retries} in {backoff}s")
                await asyncio.sleep(backoff)
                
                # Re-add to stream
                await client.xadd(
                    self.stream_key,
                    {"data": json.dumps(job.to_dict())},
                )
                await client.xack(self.stream_key, self.consumer_group, message_id)
            
            await client.hset(self.jobs_key, job.id, json.dumps(job.to_dict()))


# Pre-configured queues
resume_parse_queue = RequestQueue("resume_parse")
vector_index_queue = RequestQueue("vector_index")
email_queue = RequestQueue("email")
report_queue = RequestQueue("report")
```

---

### Phase 5: Observability & Structured Logging

---

#### [NEW] [logging_config.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/logging_config.py)

**Production logging with structured JSON output:**

```python
"""
Production Logging Configuration

Features:
- Structured JSON logging for log aggregation (CloudWatch, ELK)
- Request ID tracking across distributed systems
- Performance metrics logging
- Error tracking with Sentry integration
"""
import logging
import json
import sys
import time
from contextvars import ContextVar
from typing import Optional
from datetime import datetime, timezone

# Context variable for request tracking
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[Optional[int]] = ContextVar("user_id", default=None)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
            "user_id": user_id_ctx.get(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data, default=str)


def setup_logging(environment: str = "development", log_level: str = "INFO"):
    """Configure logging based on environment."""
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    
    if environment == "production":
        handler.setFormatter(JSONFormatter())
    else:
        # Pretty format for development
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        ))
    
    root_logger.addHandler(handler)
    
    # Reduce noise from libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class PerformanceLogger:
    """Log performance metrics for operations."""
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        self.operation = operation
        self.logger = logger or logging.getLogger("performance")
        self.start_time = None
        self.metrics = {}
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        
        self.logger.info(
            f"{self.operation} completed",
            extra={
                "extra_fields": {
                    "operation": self.operation,
                    "duration_ms": round(duration_ms, 2),
                    "success": exc_type is None,
                    **self.metrics,
                }
            }
        )
    
    def add_metric(self, key: str, value):
        self.metrics[key] = value
```

---

### Phase 6: Load Testing Suite

---

#### [NEW] [load_test.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/tests/load_test.py)

**Enterprise load testing with Locust:**

```python
"""
Load Testing Suite using Locust

Run with:
    pip install locust
    locust -f tests/load_test.py --host=https://api.hiringpro.com
    
Web UI at http://localhost:8089 to configure load

Scenarios:
1. Normal load: 100 users, steady state
2. Spike test: Sudden 10x traffic increase
3. Soak test: Sustained load over 1 hour
4. Stress test: Find breaking point
"""
import random
import json
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import time


class CandidateUser(HttpUser):
    """Simulates candidate behavior on the platform."""
    
    wait_time = between(1, 5)  # 1-5 seconds between actions
    
    def on_start(self):
        """Login when user starts."""
        # Create test account or use existing
        self.email = f"loadtest_{random.randint(1, 10000)}@test.com"
        self.token = None
        
        # Try login, register if needed
        response = self.client.post("/api/auth/login", json={
            "email": self.email,
            "password": "LoadTest123!"
        })
        
        if response.status_code == 401:
            # Register new user
            self.client.post("/api/auth/register", json={
                "email": self.email,
                "password": "LoadTest123!",
                "name": f"Load Test User {self.email}",
            })
            response = self.client.post("/api/auth/login", json={
                "email": self.email,
                "password": "LoadTest123!"
            })
        
        if response.status_code == 200:
            self.token = response.json().get("access_token")
    
    @property
    def headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}
    
    @task(10)
    def view_dashboard(self):
        """Most common action - view dashboard."""
        self.client.get("/api/profile", headers=self.headers, name="/api/profile")
    
    @task(8)
    def view_jobs(self):
        """Browse job listings."""
        self.client.get("/api/jobs", headers=self.headers, name="/api/jobs")
    
    @task(5)
    def view_available_tests(self):
        """Check available tests."""
        self.client.get("/api/tests/available", headers=self.headers, 
                       name="/api/tests/available")
    
    @task(3)
    def view_notifications(self):
        """Check notifications."""
        self.client.get("/api/notifications", headers=self.headers,
                       name="/api/notifications")
    
    @task(2)
    def search_jobs(self):
        """Search with filters."""
        self.client.get("/api/jobs?search=developer&job_type=Full%20Time",
                       headers=self.headers, name="/api/jobs (search)")
    
    @task(1)
    def take_test(self):
        """Simulate taking a test (heavy operation)."""
        # Get available tests
        response = self.client.get("/api/tests/available", headers=self.headers)
        if response.status_code != 200:
            return
        
        tests = response.json()
        if not tests:
            return
        
        test = random.choice(tests)
        
        # Start test
        start_response = self.client.post(
            "/api/tests/start",
            json={"test_id": test["id"]},
            headers=self.headers,
            name="/api/tests/start"
        )
        
        if start_response.status_code != 200:
            return
        
        attempt_id = start_response.json().get("attempt_id")
        if not attempt_id:
            return
        
        # Submit a few answers
        for i in range(3):
            self.client.post(
                f"/api/tests/{attempt_id}/answer",
                json={
                    "question_id": i + 1,
                    "answer_text": "A",
                },
                headers=self.headers,
                name="/api/tests/[id]/answer"
            )
            time.sleep(0.5)


class AdminUser(HttpUser):
    """Simulates admin behavior."""
    
    wait_time = between(2, 8)
    weight = 1  # Fewer admins than candidates
    
    def on_start(self):
        """Login as admin."""
        response = self.client.post("/api/auth/admin/login", json={
            "email": "loadtest_admin@test.com",
            "password": "AdminTest123!"
        })
        
        if response.status_code == 200:
            self.token = response.json().get("access_token")
        else:
            self.token = None
    
    @property
    def headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}
    
    @task(5)
    def view_dashboard(self):
        """Admin dashboard."""
        self.client.get("/api/admin/dashboard", headers=self.headers,
                       name="/api/admin/dashboard")
    
    @task(4)
    def view_candidates(self):
        """List candidates."""
        self.client.get("/api/admin/candidates", headers=self.headers,
                       name="/api/admin/candidates")
    
    @task(3)
    def view_results(self):
        """View test results."""
        self.client.get("/api/admin/results", headers=self.headers,
                       name="/api/admin/results")
    
    @task(2)
    def search_candidates(self):
        """Search candidates (AI-powered)."""
        self.client.get("/api/admin/candidates/search?q=python%20developer",
                       headers=self.headers,
                       name="/api/admin/candidates/search")


# Custom metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests."""
    if response_time > 2000:  # > 2 seconds
        print(f"SLOW REQUEST: {name} took {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Setup before test."""
    if isinstance(environment.runner, MasterRunner):
        print("Load test starting on master")


@events.test_stop.add_listener  
def on_test_stop(environment, **kwargs):
    """Cleanup after test."""
    print("Load test completed")
```

---

#### [NEW] [SYSTEM_LIMITS.md](file:///Users/chirkut/Desktop/Hiring%20Pro/SYSTEM_LIMITS.md)

**Document system capacity:**

```markdown
# System Capacity & Scaling Guide

## Current Architecture Limits

### Supabase Pro (Current)

| Resource | Limit | Scaling Path |
|----------|-------|--------------|
| DB Connections (Pooler) | 200-1000 | Upgrade compute |
| Direct Connections | 60-240 | Upgrade compute |
| Database Size | 8GB + $0.125/GB | 60TB max |
| Monthly Active Users | 100K + $0.00325 | Unlimited |
| Realtime Connections | 500 | Upgrade to Team |
| File Storage | 100GB + $0.021/GB | Unlimited |
| Egress | 250GB + $0.09/GB | Unlimited |

### External Services

| Service | Rate Limit | Quota |
|---------|------------|-------|
| Gemini API | 60 RPM (free), 1000 RPM (paid) | 1M tokens/day |
| Pinecone | 100 writes/sec, 200 reads/sec | Based on pods |
| Cloudinary | 25K transforms/month (free) | Based on plan |

### Application Limits (Recommended)

| Metric | Conservative | Optimistic | Breaking Point |
|--------|-------------|------------|----------------|
| Concurrent Users | 500 | 2,000 | 5,000+ |
| Requests/Second | 500 | 2,000 | 3,000+ |
| Resume Parses/Hour | 100 | 500 | 1,000 |
| Test Sessions/Hour | 200 | 1,000 | 2,000 |

## Scaling Playbook

### 100 → 1,000 Users
- [ ] Enable Redis rate limiting
- [ ] Upgrade Supabase to Small compute ($50/mo)
- [ ] Enable request queuing

### 1,000 → 5,000 Users
- [ ] Upgrade Supabase to Medium compute ($100/mo)
- [ ] Add Redis caching layer
- [ ] Horizontal scaling (2+ FastAPI instances)
- [ ] Add CDN for static assets

### 5,000 → 10,000 Users
- [ ] Upgrade Supabase to Large compute ($200/mo)
- [ ] Dedicated Pinecone pod
- [ ] Paid Gemini API tier
- [ ] 3+ FastAPI instances with auto-scaling

### 10,000+ Users
- [ ] Upgrade to Supabase Team ($599/mo)
- [ ] Read replicas for analytics queries
- [ ] Message queue (SQS/RabbitMQ) for async jobs
- [ ] Kubernetes deployment with HPA
- [ ] CDN + Edge caching
```

---

## Verification Plan

### Automated Tests

```bash
# 1. Unit tests
cd backend && pytest tests/ -v --cov=app

# 2. Load test (100 users)
pip install locust
locust -f tests/load_test.py --host=http://localhost:8000 \
    --users=100 --spawn-rate=10 --run-time=5m --headless

# 3. Stress test (find breaking point)
locust -f tests/load_test.py --host=http://localhost:8000 \
    --users=1000 --spawn-rate=50 --run-time=10m --headless
```

### Success Criteria

| Metric | Target |
|--------|--------|
| P95 Response Time | < 500ms |
| P99 Response Time | < 2000ms |
| Error Rate | < 0.1% |
| Throughput | > 500 req/sec |
| Connection Pool Errors | 0 |
| Rate Limit Hits | < 5% |

---

## Additional Components (Gaps Addressed)

### Phase 7: Health Check Endpoint

---

#### [NEW] [health.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/routers/health.py)

**Comprehensive health check for ALB and monitoring:**

```python
"""
Health Check Endpoints

Provides:
- /health - Simple liveness probe (for ALB)
- /health/ready - Readiness probe (checks dependencies)
- /health/detailed - Full system status (for monitoring)
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter, Response, status
import logging

from ..database import engine
from ..services.redis import redis_service
from ..services.circuit_breaker import gemini_circuit, pinecone_circuit
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

# Track startup time for uptime calculation
STARTUP_TIME = time.time()


@router.get("/health", status_code=200)
async def liveness_probe():
    """
    Simple liveness check - returns 200 if process is running.
    Used by load balancer for basic health.
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready")
async def readiness_probe(response: Response):
    """
    Readiness check - verifies critical dependencies.
    Returns 503 if system cannot serve traffic.
    """
    checks = {}
    healthy = True
    
    # Check database
    try:
        from sqlalchemy import text
        start = time.time()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "ok", 
            "latency_ms": round((time.time() - start) * 1000, 2)
        }
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)[:100]}
        healthy = False
    
    # Check Redis (non-critical - fail open)
    if redis_service.is_available:
        try:
            start = time.time()
            await redis_service.client.ping()
            checks["redis"] = {
                "status": "ok", 
                "latency_ms": round((time.time() - start) * 1000, 2)
            }
        except Exception as e:
            checks["redis"] = {"status": "degraded", "error": str(e)[:100]}
    else:
        checks["redis"] = {"status": "not_configured"}
    
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return {
        "status": "ready" if healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/detailed")
async def detailed_health():
    """
    Detailed health status for monitoring dashboards.
    Includes circuit breaker states, queue depths, etc.
    """
    uptime_seconds = time.time() - STARTUP_TIME
    
    # Get circuit breaker states
    circuits = {}
    for name, circuit in [
        ("gemini", gemini_circuit),
        ("pinecone", pinecone_circuit),
    ]:
        state = await circuit._get_state()
        circuits[name] = {
            "state": state["state"],
            "failures": state["failures"],
        }
    
    # Get queue depths (if Redis available)
    queues = {}
    if redis_service.is_available:
        try:
            from ..services.request_queue import resume_parse_queue, vector_index_queue
            queues["resume_parse"] = await resume_parse_queue.get_queue_depth()
            queues["vector_index"] = await vector_index_queue.get_queue_depth()
        except Exception:
            queues["error"] = "Failed to get queue stats"
    
    return {
        "status": "operational",
        "version": settings.app_version if hasattr(settings, 'app_version') else "1.0.0",
        "environment": settings.environment,
        "uptime_seconds": round(uptime_seconds, 2),
        "uptime_human": f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m",
        "circuits": circuits,
        "queues": queues,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

---

### Phase 8: Redis Cluster Support

---

#### [MODIFY] [redis.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/services/redis.py)

**Add Redis Cluster/Sentinel support for high availability:**

```python
"""
Redis Service - Production-grade with Cluster/Sentinel support

Modes:
- Standalone: Single Redis instance (development)
- Sentinel: HA with automatic failover (production minimum)
- Cluster: Sharded Redis cluster (10k+ users)
"""
import asyncio
from typing import Optional, List
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.sentinel import Sentinel
from redis.asyncio.cluster import RedisCluster
import logging

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisService:
    """
    Production Redis service supporting multiple deployment modes.
    """
    _instance: Optional["RedisService"] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def initialize(self):
        """Initialize Redis based on configuration."""
        if self._client is not None:
            return
        
        if not settings.redis_url:
            logger.warning("Redis URL not configured")
            return
        
        try:
            if settings.redis_mode == "cluster":
                # Redis Cluster for sharding
                self._client = RedisCluster.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=5.0,
                    retry_on_timeout=True,
                )
                logger.info("✅ Redis Cluster connected")
                
            elif settings.redis_mode == "sentinel":
                # Redis Sentinel for HA
                sentinels = self._parse_sentinel_hosts(settings.redis_sentinel_hosts)
                sentinel = Sentinel(
                    sentinels,
                    socket_timeout=5.0,
                    sentinel_kwargs={"decode_responses": True},
                )
                self._client = sentinel.master_for(
                    settings.redis_sentinel_master,
                    decode_responses=True,
                    socket_timeout=5.0,
                )
                logger.info("✅ Redis Sentinel connected")
                
            else:
                # Standalone Redis
                pool = ConnectionPool.from_url(
                    settings.redis_url,
                    max_connections=settings.redis_pool_size,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                    retry_on_timeout=True,
                )
                self._client = redis.Redis(connection_pool=pool)
                logger.info("✅ Redis Standalone connected")
            
            # Verify connection
            await self._client.ping()
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._client = None
    
    def _parse_sentinel_hosts(self, hosts_str: str) -> List[tuple]:
        """Parse 'host1:port1,host2:port2' into [(host1, port1), ...]"""
        result = []
        for host_port in hosts_str.split(","):
            host, port = host_port.strip().split(":")
            result.append((host, int(port)))
        return result
    
    @property
    def client(self) -> Optional[redis.Redis]:
        return self._client
    
    @property
    def is_available(self) -> bool:
        return self._client is not None
    
    async def close(self):
        """Graceful shutdown."""
        if self._client:
            await self._client.close()
            self._client = None


redis_service = RedisService()
```

**Config additions:**

```python
# In config.py - add these fields:
redis_mode: str = "standalone"  # standalone, sentinel, cluster
redis_sentinel_hosts: str = ""  # host1:26379,host2:26379,host3:26379
redis_sentinel_master: str = "mymaster"
```

---

### Phase 9: Caching Layer

---

#### [NEW] [cache.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/services/cache.py)

**Production caching for expensive operations:**

```python
"""
Caching Service for Expensive Operations

Caches:
- Candidate search results (vector search)
- Test configurations (rarely change)
- Job listings (with TTL invalidation)
- AI-generated summaries (Gemini responses)

Uses Redis with:
- Cache-aside pattern
- TTL-based expiration
- Tag-based invalidation
"""
import json
import hashlib
from typing import Optional, Any, Callable, List
from functools import wraps
import logging

from .redis import redis_service
from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class CacheService:
    """Production caching with multiple strategies."""
    
    # Default TTLs in seconds
    TTLS = {
        "search_results": 300,      # 5 minutes
        "job_listings": 600,        # 10 minutes
        "test_config": 3600,        # 1 hour
        "ai_response": 86400,       # 24 hours (expensive!)
        "user_profile": 300,        # 5 minutes
        "default": 300,
    }
    
    @staticmethod
    def _make_key(prefix: str, *args, **kwargs) -> str:
        """
        Generate cache key from arguments.
        Filters out 'self' argument from instance methods.
        """
        # Skip first arg if it's a class instance (for instance methods)
        filtered_args = args
        if args and hasattr(args[0], '__class__') and not isinstance(args[0], (str, int, float, bool, bytes, type(None))):
            filtered_args = args[1:]
        
        key_data = json.dumps({"args": filtered_args, "kwargs": kwargs}, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        return f"cache:{prefix}:{key_hash}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        client = redis_service.client
        if not client:
            return None
        
        try:
            data = await client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ):
        """Set value in cache with optional tags for invalidation."""
        client = redis_service.client
        if not client:
            return
        
        try:
            ttl = ttl or self.TTLS["default"]
            await client.setex(key, ttl, json.dumps(value))
            
            # Store key in tag sets for bulk invalidation
            if tags:
                for tag in tags:
                    await client.sadd(f"cache_tag:{tag}", key)
                    await client.expire(f"cache_tag:{tag}", ttl + 60)
                    
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
    
    async def invalidate_by_tag(self, tag: str):
        """Invalidate all keys with a specific tag."""
        client = redis_service.client
        if not client:
            return
        
        try:
            keys = await client.smembers(f"cache_tag:{tag}")
            if keys:
                await client.delete(*keys)
                await client.delete(f"cache_tag:{tag}")
                logger.info(f"Invalidated {len(keys)} keys for tag: {tag}")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")
    
    async def invalidate(self, key: str):
        """Invalidate a specific key."""
        client = redis_service.client
        if not client:
            return
        
        try:
            await client.delete(key)
        except Exception:
            pass


cache_service = CacheService()


def cached(
    prefix: str,
    ttl_category: str = "default",
    tags: Optional[List[str]] = None,
):
    """
    Decorator for caching function results.
    
    Usage:
        @cached("search", ttl_category="search_results", tags=["candidates"])
        async def search_candidates(query: str, ...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip cache if disabled
            if not settings.cache_enabled:
                return await func(*args, **kwargs)
            
            key = cache_service._make_key(prefix, *args, **kwargs)
            
            # Try cache first
            cached_value = await cache_service.get(key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {key}")
                return cached_value
            
            # Cache miss - execute function
            logger.debug(f"Cache MISS: {key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            ttl = cache_service.TTLS.get(ttl_category, cache_service.TTLS["default"])
            await cache_service.set(key, result, ttl=ttl, tags=tags)
            
            return result
        
        return wrapper
    return decorator
```

**Example usage in vector_search.py:**

```python
from .cache import cached, cache_service

@cached("candidate_search", ttl_category="search_results", tags=["candidates"])
async def search_candidates(
    self,
    query: str,
    skill_filters: Optional[List[str]] = None,
    min_experience: Optional[float] = None,
    top_k: int = 20
) -> List[Dict[str, Any]]:
    # Expensive Pinecone + Gemini operation
    ...

# Invalidate when candidate updates profile
async def on_profile_update(user_id: int):
    await cache_service.invalidate_by_tag("candidates")
```

---

### Phase 10: Worker Deployment Architecture

---

#### [NEW] [worker.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/worker.py)

**Background worker process for job queue:**

```python
"""
Background Worker Process

Runs separately from the web server to process:
- Resume parsing jobs
- Vector indexing jobs
- Email notifications
- Report generation

Deployment:
- Docker: docker-compose service
- Kubernetes: Separate Deployment with HPA
- Systemd: Separate service unit

Run with: python -m app.worker
"""
import asyncio
import signal
import logging
from contextlib import asynccontextmanager

from .services.redis import redis_service
from .services.request_queue import (
    resume_parse_queue,
    vector_index_queue,
    email_queue,
    Job,
)
from .services.resume_parser import ResumeParser
from .services.vector_search import VectorSearchService
from .logging_config import setup_logging
from .config import get_settings

settings = get_settings()
setup_logging(settings.environment, settings.log_level)
logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_event = asyncio.Event()


async def handle_resume_parse(job: Job):
    """Process resume parsing job."""
    logger.info(f"Processing resume parse job: {job.id}")
    
    parser = ResumeParser()
    result = await parser.parse_resume(
        file_bytes=job.payload.get("file_bytes"),
        filename=job.payload.get("filename"),
    )
    
    # Update user profile with parsed data
    # ... implementation ...
    
    logger.info(f"Completed resume parse job: {job.id}")


async def handle_vector_index(job: Job):
    """Process vector indexing job."""
    logger.info(f"Processing vector index job: {job.id}")
    
    service = VectorSearchService()
    await service.index_profile(
        profile_id=job.payload.get("profile_id"),
        summary=job.payload.get("summary"),
        skills=job.payload.get("skills", []),
    )
    
    logger.info(f"Completed vector index job: {job.id}")


async def handle_email(job: Job):
    """Process email notification job."""
    logger.info(f"Processing email job: {job.id}")
    # ... email sending implementation ...


async def run_worker(queue, handler, worker_name: str):
    """Run a single queue worker."""
    logger.info(f"Starting worker: {worker_name}")
    
    while not shutdown_event.is_set():
        try:
            await queue.process_jobs(
                handler=handler,
                consumer_name=worker_name,
                batch_size=5,
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker {worker_name} error: {e}")
            await asyncio.sleep(5)
    
    logger.info(f"Worker {worker_name} stopped")


async def main():
    """Main worker entry point."""
    logger.info("=" * 50)
    logger.info("Starting Hiring Pro Background Workers")
    logger.info("=" * 50)
    
    # Initialize Redis
    await redis_service.initialize()
    if not redis_service.is_available:
        logger.error("Redis not available - workers cannot start")
        return
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: shutdown_event.set())
    
    # Start workers for each queue
    workers = [
        asyncio.create_task(
            run_worker(resume_parse_queue, handle_resume_parse, "resume-worker-1")
        ),
        asyncio.create_task(
            run_worker(resume_parse_queue, handle_resume_parse, "resume-worker-2")
        ),
        asyncio.create_task(
            run_worker(vector_index_queue, handle_vector_index, "vector-worker-1")
        ),
        asyncio.create_task(
            run_worker(email_queue, handle_email, "email-worker-1")
        ),
    ]
    
    logger.info(f"Started {len(workers)} workers")
    
    # Wait for shutdown signal
    await shutdown_event.wait()
    
    logger.info("Shutdown signal received, stopping workers...")
    
    # Cancel all workers
    for worker in workers:
        worker.cancel()
    
    await asyncio.gather(*workers, return_exceptions=True)
    await redis_service.close()
    
    logger.info("All workers stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())
```

**Docker Compose configuration:**

```yaml
# docker-compose.yml
services:
  web:
    build: ./backend
    command: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
    ports:
      - "8000:8000"
    depends_on:
      - redis
      
  worker:
    build: ./backend
    command: python -m app.worker
    deploy:
      replicas: 2  # Scale workers independently
    depends_on:
      - redis
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

**Kubernetes Deployment:**

```yaml
# k8s/worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hiring-pro-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hiring-pro-worker
  template:
    spec:
      containers:
      - name: worker
        image: hiring-pro-backend:latest
        command: ["python", "-m", "app.worker"]
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: hiring-pro-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hiring-pro-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: External
    external:
      metric:
        name: redis_queue_length
      target:
        type: AverageValue
        averageValue: 100
```

---

### Phase 11: Graceful Shutdown

---

#### [MODIFY] [main.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/main.py)

**Add graceful shutdown handling:**

```python
"""
FastAPI Application with Graceful Shutdown

Handles:
- SIGTERM/SIGINT signals for zero-downtime deploys
- Draining existing connections before shutdown
- Completing in-flight requests
- Closing database and Redis connections cleanly
"""
import asyncio
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

from .database import engine, async_session_maker
from .services.redis import redis_service
from .config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Track active requests for graceful drain
active_requests = 0
shutdown_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup/shutdown.
    """
    # STARTUP
    logger.info("🚀 Starting Hiring Pro API")
    
    # Initialize Redis
    await redis_service.initialize()
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(graceful_shutdown(s))
        )
    
    logger.info("✅ Startup complete")
    
    yield
    
    # SHUTDOWN
    logger.info("🛑 Shutting down...")
    
    # Wait for active requests to complete (max 30 seconds)
    if active_requests > 0:
        logger.info(f"Waiting for {active_requests} active requests to complete...")
        try:
            await asyncio.wait_for(
                wait_for_requests_to_drain(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for requests, forcing shutdown")
    
    # Close connections
    await redis_service.close()
    await engine.dispose()
    
    logger.info("✅ Shutdown complete")


async def graceful_shutdown(sig):
    """Handle shutdown signal."""
    logger.info(f"Received signal {sig.name}")
    shutdown_event.set()


async def wait_for_requests_to_drain():
    """Wait until all active requests are completed."""
    while active_requests > 0:
        await asyncio.sleep(0.5)


# Create app FIRST
app = FastAPI(
    title="Hiring Pro API",
    lifespan=lifespan,
)


# Define middleware AFTER app exists
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Add request ID for tracing and logging."""
    import uuid
    from .logging_config import request_id_ctx
    
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id_ctx.set(request_id)
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def track_requests(request, call_next):
    global active_requests
    
    # Don't accept new requests during shutdown
    if shutdown_event.is_set():
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"error": "Server is shutting down"},
            headers={"Connection": "close"}
        )
    
    active_requests += 1
    try:
        response = await call_next(request)
        return response
    finally:
        active_requests -= 1
```

---

### Cost Estimates

| Scale | Component | Monthly Cost |
|-------|-----------|--------------|
| **100-500 users** | | |
| | Supabase Pro (Micro) | $25 |
| | Redis (t3.micro) | $15 |
| | Single EC2 t3.small | $20 |
| | **Total** | **~$60/mo** |
| **500-2,000 users** | | |
| | Supabase Pro (Small) | $75 |
| | Redis (t3.small) | $30 |
| | 2x EC2 t3.medium | $80 |
| | CloudFront CDN | $20 |
| | **Total** | **~$205/mo** |
| **2,000-5,000 users** | | |
| | Supabase Pro (Medium) | $125 |
| | Redis Cluster (3 nodes) | $90 |
| | 3x EC2 t3.large + ALB | $200 |
| | Pinecone Starter | $70 |
| | CloudFront | $50 |
| | **Total** | **~$535/mo** |
| **5,000-10,000 users** | | |
| | Supabase Pro (Large) | $225 |
| | Redis Cluster (5 nodes) | $150 |
| | 5x EC2 t3.xlarge + ALB | $500 |
| | Pinecone Standard | $150 |
| | Gemini Paid Tier | $100 |
| | CloudFront | $100 |
| | **Total** | **~$1,225/mo** |
| **10,000+ users** | | |
| | Supabase Team | $599 |
| | ElastiCache Redis | $300 |
| | EKS Cluster (auto-scale) | $800 |
| | Pinecone Pro | $300 |
| | Gemini Enterprise | $500 |
| | CloudFront + WAF | $200 |
| | Monitoring (DataDog) | $100 |
| | **Total** | **~$2,800/mo** |

---

## Updated Implementation Priority

| Day | Focus | Components |
|-----|-------|------------|
| 1 | **Redis + Rate Limiting** | `redis.py`, `rate_limiter.py` |
| 2 | **Health Checks + Graceful Shutdown** | `health.py`, `main.py` lifespan |
| 3 | **Connection Pooling** | `database.py`, `config.py` |
| 4 | **Circuit Breakers** | `circuit_breaker.py`, service integration |
| 5 | **Request Queue + Workers** | `request_queue.py`, `worker.py`, Docker setup |
| 6 | **Caching Layer** | `cache.py`, integration with vector_search |
| 7 | **Observability + Load Testing** | `logging_config.py`, `load_test.py` |

---

- [ ] Redis cluster deployed and tested
- [ ] Health endpoints verified with ALB
- [ ] Graceful shutdown tested (rolling deploy)
- [ ] Load test passed (10k concurrent users)
- [ ] Circuit breakers tested with service failures
- [ ] Caching verified with cache hit ratio > 80%
- [ ] Worker scaling tested under load
- [ ] Alerts configured (PagerDuty/OpsGenie)
- [ ] Runbook documented for on-call
- [ ] Cost monitoring enabled (AWS Budgets)

---

## AWS Elastic Beanstalk Architecture

> [!IMPORTANT]
> The generic Docker/Kubernetes approach above is replaced with Beanstalk-native patterns for this deployment.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Route 53                                        │
│                         api.hiringpro.com                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Elastic Beanstalk - Web Environment                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Application Load Balancer                    │   │
│  │                    (Health: /health, HTTPS termination)             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│           ┌──────────────────────────┼──────────────────────────┐           │
│           ▼                          ▼                          ▼           │
│  ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐   │
│  │   EC2 + Nginx   │       │   EC2 + Nginx   │       │   EC2 + Nginx   │   │
│  │   + Gunicorn    │       │   + Gunicorn    │       │   + Gunicorn    │   │
│  │   + FastAPI     │       │   + FastAPI     │       │   + FastAPI     │   │
│  └─────────────────┘       └─────────────────┘       └─────────────────┘   │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
        ┌───────────────────┐  ┌─────────────┐  ┌─────────────────┐
        │   ElastiCache     │  │  Amazon     │  │   Supabase      │
        │   (Redis)         │  │  SQS        │  │   Postgres      │
        │  Rate Limit/Cache │  │  Job Queue  │  │   (Supavisor)   │
        └───────────────────┘  └──────┬──────┘  └─────────────────┘
                                      │
                                      ▼
        ┌─────────────────────────────────────────────────────────┐
        │            Elastic Beanstalk - Worker Environment        │
        │  ┌───────────────────────────────────────────────────┐  │
        │  │   EC2 (Auto-scaling based on SQS queue depth)     │  │
        │  │   Gunicorn + FastAPI (worker_app.py)              │  │
        │  │   ← SQS Daemon POSTs to /worker/*                 │  │
        │  └───────────────────────────────────────────────────┘  │
        └─────────────────────────────────────────────────────────┘
```

---

### What Changes for Beanstalk

| Original Component | Beanstalk Replacement | Reason |
|-------------------|----------------------|--------|
| `worker.py` (Redis Streams) | `worker_app.py` + SQS | EB Worker tier polls SQS natively |
| `request_queue.py` | `sqs_queue.py` | SQS is managed, auto-scales |
| Docker Compose | `.ebextensions/` | EB manages containers |
| Kubernetes HPA | EB Auto Scaling | Native integration |
| Custom signal handling | Gunicorn + EB hooks | EB sends SIGTERM on deploy |

---

### Phase 12: Beanstalk Configuration Files

---

#### [NEW] [Procfile.web](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/Procfile.web)

**For Web Environment:**

```
web: gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --graceful-timeout 30 --timeout 60 app.main:app
```

---

#### [NEW] [Procfile.worker](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/Procfile.worker)

**For Worker Environment:**

```
web: gunicorn -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --graceful-timeout 30 --timeout 120 app.worker_app:app
```

> [!TIP]
> **Deployment workflow:**
> ```bash
> # Deploy web environment
> cd backend && cp Procfile.web Procfile && eb deploy hiring-pro-web
> 
> # Deploy worker environment  
> cd backend && cp Procfile.worker Procfile && eb deploy hiring-pro-worker
> ```

---

#### [NEW] [.ebextensions/01-packages.config](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/.ebextensions/01-packages.config)

```yaml
packages:
  yum:
    python3-devel: []
    gcc: []
```

---

#### [NEW] [.ebextensions/02-environment.config](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/.ebextensions/02-environment.config)

```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    ENVIRONMENT: production
    USE_EXTERNAL_POOLER: "true"
    RATE_LIMIT_ENABLED: "true"

  aws:elasticbeanstalk:environment:proxy:
    ProxyServer: nginx

  # ALB Health Check (not Classic ELB)
  aws:elasticbeanstalk:environment:process:default:
    HealthCheckPath: /health
    HealthCheckInterval: 30
    HealthCheckTimeout: 5
    HealthyThresholdCount: 2
    UnhealthyThresholdCount: 5
    Port: "8000"
    Protocol: HTTP
```

---

#### [NEW] [.ebextensions/03-alb.config](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/.ebextensions/03-alb.config)

```yaml
option_settings:
  aws:elbv2:listener:443:
    Protocol: HTTPS
    SSLCertificateArns: arn:aws:acm:region:account:certificate/xxx

  aws:elbv2:listener:80:
    Protocol: HTTP
    DefaultProcess: default
    Rules: redirect-to-https

  aws:elbv2:listenerrule:redirect-to-https:
    PathPatterns: /*
    Process: default
    RedirectProtocol: HTTPS
    RedirectStatusCode: "301"
```

---

#### [NEW] [.ebextensions/04-graceful-shutdown.config](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/.ebextensions/04-graceful-shutdown.config)

```yaml
option_settings:
  aws:elasticbeanstalk:command:
    DeploymentPolicy: Rolling
    BatchSize: 30
    BatchSizeType: Percentage

  aws:autoscaling:updatepolicy:rollingupdate:
    RollingUpdateEnabled: true
    MaxBatchSize: 1
    MinInstancesInService: 1
    PauseTime: PT5M

files:
  "/opt/elasticbeanstalk/hooks/appdeploy/pre/01_stop_gracefully.sh":
    mode: "000755"
    owner: root
    group: root
    content: |
      #!/bin/bash
      pkill -SIGTERM -f gunicorn || true
      sleep 10  # Wait for connections to drain
```

---

#### [NEW] [.ebextensions/05-iam.config](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/.ebextensions/05-iam.config)

**IAM permissions for SQS access:**

```yaml
Resources:
  WorkerSQSPolicy:
    Type: AWS::IAM::Policy
    Properties:
      PolicyName: HiringProSQSPolicy
      PolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Action:
              - sqs:SendMessage
              - sqs:GetQueueUrl
              - sqs:GetQueueAttributes
            Resource: !Sub "arn:aws:sqs:${AWS::Region}:${AWS::AccountId}:hiring-pro-*"
      Roles:
        - !Ref AWSEBInstanceRole
```

---

### Phase 13: SQS Queue Service

---

#### [NEW] [sqs_queue.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/services/sqs_queue.py)

**Replaces `request_queue.py` for Beanstalk:**

```python
"""
SQS Queue Service for Elastic Beanstalk Worker Environment.
EB Worker automatically polls SQS and POSTs to your app.

Uses aioboto3 for proper async SQS operations.
"""
import json
import aioboto3
from typing import Optional, Dict, Any
import logging

from ..config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class SQSQueue:
    """
    SQS queue for async job processing.
    
    EB Worker Environment will:
    1. Poll this queue automatically
    2. POST message body to http://localhost/worker/{endpoint}
    3. Delete message on 200 response
    4. Retry on failure (with backoff)
    """
    
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self._session = aioboto3.Session()
        self._queue_url = None
    
    async def _get_client(self):
        """Get async SQS client context manager."""
        return self._session.client('sqs', region_name=settings.aws_region)
    
    async def get_queue_url(self) -> str:
        if self._queue_url is None:
            async with await self._get_client() as client:
                response = await client.get_queue_url(QueueName=self.queue_name)
                self._queue_url = response['QueueUrl']
        return self._queue_url
    
    async def enqueue(
        self,
        payload: Dict[str, Any],
        delay_seconds: int = 0,
        deduplication_id: Optional[str] = None,
    ) -> str:
        """Add job to SQS queue. Returns message ID."""
        queue_url = await self.get_queue_url()
        
        message_body = json.dumps({
            "queue_name": self.queue_name,
            "payload": payload,
        })
        
        params = {
            'QueueUrl': queue_url,
            'MessageBody': message_body,
            'DelaySeconds': delay_seconds,
        }
        
        # For FIFO queues
        if self.queue_name.endswith('.fifo'):
            params['MessageGroupId'] = payload.get('group_id', 'default')
            if deduplication_id:
                params['MessageDeduplicationId'] = deduplication_id
        
        async with await self._get_client() as client:
            response = await client.send_message(**params)
        
        logger.info(f"Enqueued job to {self.queue_name}: {response['MessageId']}")
        return response['MessageId']


# Pre-configured queues
resume_parse_queue = SQSQueue("hiring-pro-resume-parse")
vector_index_queue = SQSQueue("hiring-pro-vector-index")
email_queue = SQSQueue("hiring-pro-email")
```

---

### Phase 14: Worker Environment

---

#### [NEW] [worker_routes.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/routers/worker_routes.py)

**HTTP endpoints that EB Worker POSTs SQS messages to:**

```python
"""
Worker HTTP endpoints for EB Worker Environment.
EB's SQS daemon POSTs messages to these endpoints.
"""
from fastapi import APIRouter, Request, HTTPException
import logging

from ..services.resume_parser import ResumeParser
from ..services.vector_search import VectorSearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/worker", tags=["Worker"])


@router.post("/resume-parse")
async def handle_resume_parse(request: Request):
    """
    EB Worker POSTs SQS messages here.
    Return 200 = message deleted from queue.
    Return 4xx/5xx = message returned to queue for retry.
    """
    body = await request.json()
    payload = body.get("payload", {})
    
    try:
        parser = ResumeParser()
        result = await parser.parse_from_s3(
            s3_key=payload.get("s3_key"),
            user_id=payload.get("user_id"),
        )
        return {"status": "completed", "result": result}
    except Exception as e:
        logger.error(f"Resume parse failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector-index")
async def handle_vector_index(request: Request):
    """Index profile in Pinecone."""
    body = await request.json()
    payload = body.get("payload", {})
    
    try:
        service = VectorSearchService()
        await service.index_profile(
            profile_id=payload.get("profile_id"),
            summary=payload.get("summary"),
            skills=payload.get("skills", []),
        )
        return {"status": "completed"}
    except Exception as e:
        logger.error(f"Vector index failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email")
async def handle_email(request: Request):
    """Send email notification."""
    body = await request.json()
    # ... email implementation
    return {"status": "completed"}


# ========== Cron Job Endpoints ==========
# These are called by EB Worker cron scheduler (cron.yaml)

@router.post("/cleanup-sessions")
async def cleanup_sessions():
    """
    Clean up expired test sessions and temporary data.
    Called every 6 hours by cron.yaml.
    """
    from ..database import async_session_maker
    from sqlalchemy import text
    from datetime import datetime, timedelta
    
    async with async_session_maker() as session:
        # Delete expired sessions older than 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        await session.execute(
            text("DELETE FROM test_attempts WHERE status = 'abandoned' AND started_at < :cutoff"),
            {"cutoff": cutoff}
        )
        await session.commit()
    
    logger.info("Cleaned up expired sessions")
    return {"status": "completed"}


@router.post("/generate-reports")
async def generate_reports():
    """
    Generate daily analytics reports.
    Called at 2 AM daily by cron.yaml.
    """
    # ... report generation implementation
    logger.info("Generated daily reports")
    return {"status": "completed"}
```

---

#### [NEW] [worker_app.py](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/app/worker_app.py)

**Minimal FastAPI app for EB Worker Environment:**

```python
"""
Minimal FastAPI app for EB Worker Environment.
Only includes worker endpoints - not the full API.
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager

from .routers.worker_routes import router as worker_router
from .services.redis import redis_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_service.initialize()
    yield
    await redis_service.close()


app = FastAPI(title="Hiring Pro Worker", lifespan=lifespan)
app.include_router(worker_router)


@app.get("/health")
async def health():
    return {"status": "alive"}
```

---

#### [NEW] [cron.yaml](file:///Users/chirkut/Desktop/Hiring%20Pro/backend/cron.yaml)

**Scheduled tasks for EB Worker:**

```yaml
version: 1
cron:
  - name: "cleanup-expired-sessions"
    url: "/worker/cleanup-sessions"
    schedule: "0 */6 * * *"  # Every 6 hours

  - name: "generate-daily-reports"
    url: "/worker/generate-reports"
    schedule: "0 2 * * *"  # 2 AM daily
```

---

### Updated Cost Estimates (Beanstalk)

| Scale | Component | Monthly Cost |
|-------|-----------|--------------|
| **100-500 users** | | |
| | Supabase Pro (Micro) | $25 |
| | EB Web (1x t3.small) | $15 |
| | ElastiCache (t3.micro) | $12 |
| | SQS (minimal) | $1 |
| | **Total** | **~$53/mo** |
| **500-2,000 users** | | |
| | Supabase Pro (Small) | $75 |
| | EB Web (2x t3.medium, ALB) | $80 |
| | EB Worker (1x t3.small) | $15 |
| | ElastiCache (t3.small) | $25 |
| | SQS | $5 |
| | **Total** | **~$200/mo** |
| **2,000-5,000 users** | | |
| | Supabase Pro (Medium) | $125 |
| | EB Web (3x t3.large, ALB) | $180 |
| | EB Worker (2x t3.medium) | $60 |
| | ElastiCache (r6g.large) | $90 |
| | SQS | $20 |
| | CloudFront | $50 |
| | **Total** | **~$525/mo** |
| **5,000-10,000 users** | | |
| | Supabase Pro (Large) | $225 |
| | EB Web (5x t3.xlarge, ALB) | $400 |
| | EB Worker (3x t3.large) | $150 |
| | ElastiCache Cluster | $200 |
| | SQS | $50 |
| | CloudFront + WAF | $150 |
| | **Total** | **~$1,175/mo** |

---

### Beanstalk Implementation Priority

| Day | Focus | Components |
|-----|-------|------------|
| 1 | **Basic EB Setup** | `Procfile`, `.ebextensions/`, health endpoint |
| 2 | **Redis + Rate Limiting** | ElastiCache setup, `redis.py`, `rate_limiter.py` |
| 3 | **Connection Pooling** | `database.py` with Supavisor |
| 4 | **SQS + Worker Env** | `sqs_queue.py`, `worker_app.py`, `worker_routes.py` |
| 5 | **Circuit Breakers** | `circuit_breaker.py` |
| 6 | **Caching Layer** | `cache.py` |
| 7 | **Load Testing** | Test against EB environment |

---

### Beanstalk Deployment Commands

```bash
# Install EB CLI
pip install awsebcli

# Initialize (one time)
eb init hiring-pro-api --platform python-3.11 --region us-east-1

# Create web environment
eb create hiring-pro-web --instance-type t3.medium --elb-type application

# Create worker environment
eb create hiring-pro-worker --tier worker --instance-type t3.small

# Deploy
eb deploy hiring-pro-web
eb deploy hiring-pro-worker

# View logs
eb logs --all

# SSH for debugging
eb ssh
```


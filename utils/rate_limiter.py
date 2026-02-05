"""Rate limiting configuration for API endpoints."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Create limiter instance
limiter = Limiter(key_func=get_remote_address)

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors."""
    logger.warning(
        f"Rate limit exceeded for {get_remote_address(request)}",
        extra={
            "client_ip": get_remote_address(request),
            "path": request.url.path,
            "limit": str(exc.detail)
        }
    )
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": "60 seconds"
        }
    )

# Rate limit configurations
RATE_LIMITS = {
    "inventory_trigger": "10/minute",
    "debug": "30/minute",
    "batch": "5/minute",
    "orders": "60/minute"
}

"""Health check endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter
from src.models.response import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Service health check endpoint (GITHUB-GUIDE.md §11)."""
    return HealthResponse(
        status="healthy",
        service="returns-manager",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

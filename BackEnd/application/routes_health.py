"""
routes_health.py — Health-check endpoint.

GET /api/health
  → { "status": "ok" }

Used by the frontend to determine whether the Python backend is running
before showing the scrape form.
"""

from fastapi import APIRouter
from application.models import HealthResponse

router = APIRouter()


@router.get("/api/health", response_model=HealthResponse, tags=["Health"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")

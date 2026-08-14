""" routes_quota.py — Quota status endpoints. """
from fastapi import APIRouter
from application import quota_service
from application.models import QuotaResponse

router = APIRouter()

@router.get("/api/quota", response_model=QuotaResponse, tags=["Quota"])
async def get_quota():
    """Get current daily quota usage."""
    return quota_service.get_quota_for_frontend()
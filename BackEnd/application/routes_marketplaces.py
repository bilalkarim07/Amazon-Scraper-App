""" routes_marketplaces.py — Marketplace configuration endpoints. """

from fastapi import APIRouter
from application.marketplace_config import get_all_marketplaces

router = APIRouter()

@router.get("/api/marketplaces", tags=["Marketplaces"])
async def get_marketplaces():
    """Return all available marketplace configurations."""
    return get_all_marketplaces()
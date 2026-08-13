"""
models.py — Pydantic request/response shapes for the FastAPI routes.

Only what Phase 1 needs.  No ORM models here — those live in job_service.py.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Job creation
# ---------------------------------------------------------------------------

class JobCreateResponse(BaseModel):
    job_id: str
    status: str


# ---------------------------------------------------------------------------
# Job status / detail
# ---------------------------------------------------------------------------

class JobStatusResponse(BaseModel):
    id: str
    status: str                      # created | running | completed | failed
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_rows: int = 0
    processed_rows: int = 0
    output_file: Optional[str] = None
    error: Optional[str] = None

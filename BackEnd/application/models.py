""" models.py — Pydantic request/response shapes. """

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str

class JobCreateResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    id: str
    status: str  # created | running | cancelling | cancelled | completed | failed
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    total_rows: int = 0
    processed_rows: int = 0
    output_file: Optional[str] = None
    error: Optional[str] = None

class CancelResponse(BaseModel):
    job_id: str
    status: str  # cancelling
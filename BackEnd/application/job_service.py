""" job_service.py — SQLite CRUD layer for the `jobs` table. """

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from application.database import get_connection

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _row_to_dict(row) -> dict:
    return dict(row)

def create_job(total_rows: int = 0) -> dict:
    job_id = str(uuid.uuid4())
    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO jobs (id, status, created_at, total_rows) VALUES (?, ?, ?, ?)",
            (job_id, "created", now, total_rows),
        )
        conn.commit()
    return get_job(job_id)

def get_job(job_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None

def update_job(job_id: str, **fields) -> Optional[dict]:
    if not fields:
        return get_job(job_id)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [job_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
        conn.commit()
    return get_job(job_id)

def list_jobs() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]

# --- Convenience status helpers ---

def mark_running(job_id: str) -> Optional[dict]:
    return update_job(job_id, status="running", started_at=_now_iso())

def mark_completed(job_id: str, output_file: str, processed_rows: int) -> Optional[dict]:
    return update_job(
        job_id,
        status="completed",
        completed_at=_now_iso(),
        output_file=output_file,
        processed_rows=processed_rows,
    )

def mark_failed(job_id: str, error: str) -> Optional[dict]:
    return update_job(
        job_id,
        status="failed",
        completed_at=_now_iso(),
        error=error,
    )

def mark_cancelling(job_id: str) -> Optional[dict]:
    return update_job(job_id, status="cancelling")

def mark_cancelled(job_id: str, processed_rows: int = 0) -> Optional[dict]:
    return update_job(
        job_id,
        status="cancelled",
        cancelled_at=_now_iso(),
        processed_rows=processed_rows,
    )

def update_progress(job_id: str, processed_rows: int) -> Optional[dict]:
    return update_job(job_id, processed_rows=processed_rows)
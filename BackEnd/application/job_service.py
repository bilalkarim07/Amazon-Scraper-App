"""
job_service.py — SQLite CRUD layer for the `jobs` table.

All database interaction for jobs goes through this module.
FastAPI routes and services should never write raw SQL themselves.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from application.database import get_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_job(total_rows: int = 0) -> dict:
    """
    Insert a new job record with status='created' and return the full row as a dict.
    """
    job_id = str(uuid.uuid4())
    now = _now_iso()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, status, created_at, total_rows)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, "created", now, total_rows),
        )
        conn.commit()

    return get_job(job_id)


def get_job(job_id: str) -> Optional[dict]:
    """Return a job dict, or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def update_job(job_id: str, **fields) -> Optional[dict]:
    """
    Partial update for a job row.

    Example:
        update_job(job_id, status="running", started_at=_now_iso())
    """
    if not fields:
        return get_job(job_id)

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [job_id]

    with get_connection() as conn:
        conn.execute(
            f"UPDATE jobs SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()

    return get_job(job_id)


def list_jobs() -> list[dict]:
    """Return all jobs, most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Convenience status helpers
# ---------------------------------------------------------------------------

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

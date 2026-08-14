""" quota_service.py — Persistent daily scraping quota management. """
from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from application.database import get_connection
from application.config import DAILY_QUOTA_LIMIT


def get_quota() -> dict:
    """Get current quota status."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT daily_limit, used, quota_date, last_updated FROM quota WHERE id = 1"
        ).fetchone()
        if not row:
            # Initialize if missing
            today = date.today().isoformat()
            conn.execute(
                "INSERT INTO quota (id, daily_limit, used, quota_date) VALUES (1, ?, 0, ?)",
                (DAILY_QUOTA_LIMIT, today)
            )
            conn.commit()
            row = conn.execute(
                "SELECT daily_limit, used, quota_date, last_updated FROM quota WHERE id = 1"
            ).fetchone()
        
        today = date.today().isoformat()
        used = row["used"]
        quota_date = row["quota_date"]
        
        # Reset if new day
        if quota_date != today:
            used = 0
            conn.execute(
                "UPDATE quota SET used = 0, quota_date = ?, last_updated = CURRENT_TIMESTAMP WHERE id = 1",
                (today,)
            )
            conn.commit()
        
        return {
            "daily_limit": row["daily_limit"],
            "used": used,
            "remaining": row["daily_limit"] - used,
            "quota_date": today,
            "last_updated": row["last_updated"]
        }


def reserve_quota(requested_rows: int) -> tuple[bool, Optional[str]]:
    """
    Atomically reserve quota for a job.
    Returns (success, error_message).
    """
    if requested_rows <= 0:
        return False, "Requested rows must be greater than 0"
    
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        
        # Get current quota
        row = conn.execute(
            "SELECT daily_limit, used, quota_date FROM quota WHERE id = 1"
        ).fetchone()
        
        today = date.today().isoformat()
        used = row["used"]
        daily_limit = row["daily_limit"]
        
        # Reset if new day
        if row["quota_date"] != today:
            used = 0
            conn.execute(
                "UPDATE quota SET used = 0, quota_date = ? WHERE id = 1",
                (today,)
            )
        
        # Check if enough quota remains
        remaining = daily_limit - used
        if requested_rows > remaining:
            conn.rollback()
            return False, f"Quota exceeded. Daily limit: {daily_limit}, Used: {used}, Remaining: {remaining}, Requested: {requested_rows}"
        
        # Reserve the quota
        conn.execute(
            "UPDATE quota SET used = used + ?, last_updated = CURRENT_TIMESTAMP WHERE id = 1",
            (requested_rows,)
        )
        conn.commit()
        return True, None


def release_quota(rows_to_release: int) -> None:
    """
    Release unused quota after job completion.
    Called with (requested_rows - actual_processed).
    """
    if rows_to_release <= 0:
        return
    
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE quota SET used = used - ? WHERE id = 1 AND used >= ?",
            (rows_to_release, rows_to_release)
        )
        conn.commit()


def get_quota_for_frontend() -> dict:
    """Get quota data formatted for frontend display."""
    quota = get_quota()
    return {
        "limit": quota["daily_limit"],
        "used": quota["used"],
        "remaining": quota["remaining"],
        "date": quota["quota_date"]
    }
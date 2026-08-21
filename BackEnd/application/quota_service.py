""" quota_service.py — Persistent daily scraping quota management. """
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from application.database import get_connection
from application.config import DAILY_QUOTA_LIMIT
from application import job_service

logger = logging.getLogger(__name__)


def _now_utc_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_to_utc(iso_str: str) -> datetime:
    """Parse ISO-8601 string to timezone-aware UTC datetime."""
    if iso_str is None:
        return datetime.now(timezone.utc)
    # Handle SQLite's default format: YYYY-MM-DD HH:MM:SS
    try:
        dt = datetime.fromisoformat(iso_str)
    except ValueError:
        # Try SQLite format
        dt = datetime.strptime(iso_str, "%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def check_and_reset_quota() -> dict:
    """
    Central authoritative quota maintenance function.

    Checks if the 24-hour window has expired. If so, resets used=0 and updates
    window_started_at. Returns the current quota row as a dict.

    This function is safe to call from within an existing transaction.
    """
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT id, daily_limit, used, reserved, quota_date, window_started_at, last_updated
            FROM quota WHERE id = 1
        """).fetchone()

        if not row:
            now_utc = _now_utc_iso()
            today = datetime.now(timezone.utc).date().isoformat()
            conn.execute("""
                INSERT INTO quota (id, daily_limit, used, reserved, quota_date, window_started_at)
                VALUES (1, ?, 0, 0, ?, ?)
            """, (DAILY_QUOTA_LIMIT, today, now_utc))
            conn.commit()
            row = conn.execute("SELECT * FROM quota WHERE id = 1").fetchone()

        window_start = _parse_iso_to_utc(row["window_started_at"])
        now = datetime.now(timezone.utc)
        elapsed = now - window_start

        if elapsed >= timedelta(hours=24):
            new_window_start = _now_utc_iso()
            conn.execute("""
                UPDATE quota
                SET used = 0,
                    window_started_at = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (new_window_start,))
            conn.commit()
            logger.info(
                "[QUOTA] Quota window expired (%.1f hours ago); resetting usage to 0",
                elapsed.total_seconds() / 3600.0
            )
            row = conn.execute("SELECT * FROM quota WHERE id = 1").fetchone()
        else:
            remaining_hours = 24 - elapsed.total_seconds() / 3600.0
            logger.debug(
                "[QUOTA] Window active: %.1f hours remaining",
                remaining_hours
            )

        return dict(row)


def get_quota() -> dict:
    """Get current quota status, ensuring window is current."""
    quota_row = check_and_reset_quota()
    return {
        "daily_limit": quota_row["daily_limit"],
        "used": quota_row["used"],
        "remaining": quota_row["daily_limit"] - quota_row["used"],
        "quota_date": datetime.now(timezone.utc).date().isoformat(),
        "last_updated": quota_row["last_updated"],
        "window_started_at": quota_row["window_started_at"],
        "reserved": quota_row.get("reserved", 0),
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

        row = conn.execute("""
            SELECT id, daily_limit, used, reserved, window_started_at
            FROM quota WHERE id = 1
        """).fetchone()

        if not row:
            now_utc = _now_utc_iso()
            today = datetime.now(timezone.utc).date().isoformat()
            conn.execute("""
                INSERT INTO quota (id, daily_limit, used, reserved, quota_date, window_started_at)
                VALUES (1, ?, 0, 0, ?, ?)
            """, (DAILY_QUOTA_LIMIT, today, now_utc))
            conn.commit()
            row = conn.execute("""
                SELECT id, daily_limit, used, reserved, window_started_at
                FROM quota WHERE id = 1
            """).fetchone()

        window_start = _parse_iso_to_utc(row["window_started_at"])
        now = datetime.now(timezone.utc)
        elapsed = now - window_start

        if elapsed >= timedelta(hours=24):
            new_window_start = _now_utc_iso()
            conn.execute("""
                UPDATE quota
                SET used = 0,
                    window_started_at = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (new_window_start,))
            row = conn.execute("""
                SELECT id, daily_limit, used, reserved, window_started_at
                FROM quota WHERE id = 1
            """).fetchone()
            logger.info("[QUOTA] Quota window expired; reset during reservation")

        daily_limit = row["daily_limit"]
        used = row["used"]
        remaining = daily_limit - used

        if requested_rows > remaining:
            conn.rollback()
            logger.warning(
                "[QUOTA] Quota exceeded: limit=%d, used=%d, requested=%d",
                daily_limit, used, requested_rows
            )
            return False, (
                f"Quota exceeded. Daily limit: {daily_limit}, "
                f"Used: {used}, Remaining: {remaining}, Requested: {requested_rows}"
            )

        conn.execute("""
            UPDATE quota
            SET used = used + ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (requested_rows,))

        conn.commit()
        logger.info("[QUOTA] Reserved %d rows (used=%d, remaining=%d)",
                    requested_rows, used + requested_rows, remaining - requested_rows)
        return True, None


def release_quota(rows_to_release: int) -> None:
    """Release unused quota after job completion."""
    if rows_to_release <= 0:
        return

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            UPDATE quota
            SET used = used - ?
            WHERE id = 1 AND used >= ?
        """, (rows_to_release, rows_to_release))
        conn.commit()
        logger.info("[QUOTA] Released %d unused rows", rows_to_release)


def get_quota_for_frontend() -> dict:
    quota = get_quota()
    return {
        "limit": quota["daily_limit"],
        "used": quota["used"],
        "remaining": quota["remaining"],
        "date": quota["quota_date"],
        "window_started_at": quota["window_started_at"],
    }


def consume_quota(rows_to_consume: int) -> bool:
    """
    Atomically consume a specific number of quota rows.
    Returns True if successful, False if insufficient remaining quota.
    """
    if rows_to_consume < 0:
        return False
    if rows_to_consume == 0:
        return True

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT daily_limit, used, window_started_at
            FROM quota WHERE id = 1
        """).fetchone()

        window_start = _parse_iso_to_utc(row["window_started_at"])
        now = datetime.now(timezone.utc)
        if now - window_start >= timedelta(hours=24):
            new_window_start = _now_utc_iso()
            conn.execute("""
                UPDATE quota
                SET used = 0,
                    window_started_at = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (new_window_start,))
            row = conn.execute("SELECT daily_limit, used FROM quota WHERE id = 1").fetchone()

        daily_limit = row["daily_limit"]
        used = row["used"]
        remaining = daily_limit - used

        if rows_to_consume > remaining:
            conn.rollback()
            return False

        conn.execute("UPDATE quota SET used = used + ? WHERE id = 1", (rows_to_consume,))
        conn.commit()
        return True


def settle_quota(job_id: str, requested_rows: int, successful_rows: int) -> None:
    """
    Idempotently release unused rows that were reserved but not successfully processed.
    Does NOT consume quota because reserve_quota() already added to used.

    For Quick Scrape jobs, this function does nothing (no quota was reserved).

    Uses the job's quota_settled flag to guarantee idempotency.
    """
    # ---- Quick Scrape check ----
    job = job_service.get_job(job_id)
    if not job:
        logger.warning("[QUOTA] Job %s not found; skipping settlement", job_id)
        return
    if job.get("quick_scrape", False):
        logger.info("[QUOTA] Skipping quota settlement for quick scrape job %s", job_id)
        return

    # ---- Idempotency check ----
    if job.get("quota_settled", 0) == 1:
        logger.info("[QUOTA] Quota already settled for job %s", job_id)
        return

    if requested_rows <= 0:
        return

    successful_rows = max(0, min(successful_rows, requested_rows))
    unused_rows = requested_rows - successful_rows

    # ---- Perform settlement atomically ----
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        # Release unused rows if any
        if unused_rows > 0:
            conn.execute(
                "UPDATE quota SET used = used - ? WHERE id = 1 AND used >= ?",
                (unused_rows, unused_rows)
            )
            logger.info("[QUOTA] Released %d unused rows for job %s", unused_rows, job_id)

        # Update job: mark quota_settled = 1 and set quota_used = successful_rows
        # This is the critical idempotency guard.
        conn.execute(
            """UPDATE jobs 
               SET quota_settled = 1, quota_used = ? 
               WHERE id = ? AND quota_settled = 0""",
            (successful_rows, job_id)
        )
        if conn.total_changes == 0:
            # Race: another process already settled; rollback to be safe
            conn.rollback()
            logger.warning("[QUOTA] Settlement race detected for job %s; rolling back", job_id)
            return

        conn.commit()
        logger.info("[QUOTA] Settled job %s: requested=%d, successful=%d, quota_used=%d",
                    job_id, requested_rows, successful_rows, successful_rows)


def release_reserved(job_id: str, requested_rows: int) -> None:
    """
    Release all previously reserved quota for a job that failed.

    For Quick Scrape jobs, this function does nothing (no quota was reserved).
    This function is idempotent via quota_settled.
    """
    job = job_service.get_job(job_id)
    if not job:
        return
    if job.get("quick_scrape", False):
        logger.info("[QUOTA] Skipping release of reserved quota for quick scrape job %s", job_id)
        return
    if job.get("quota_settled", 0) == 1:
        logger.info("[QUOTA] Quota already settled for job %s; release skipped", job_id)
        return
    if requested_rows <= 0:
        return

    # Atomically release and mark settled
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE quota SET used = used - ? WHERE id = 1 AND used >= ?",
            (requested_rows, requested_rows)
        )
        conn.execute(
            "UPDATE jobs SET quota_settled = 1, quota_used = 0 WHERE id = ? AND quota_settled = 0",
            (job_id,)
        )
        conn.commit()
    logger.info("[QUOTA] Released all reserved quota for failed job %s: %d rows",
                job_id, requested_rows)
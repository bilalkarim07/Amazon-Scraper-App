""" database.py — SQLite setup. """
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from application.config import DB_PATH

_CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT,
    input_file TEXT,
    output_file TEXT,
    total_rows INTEGER DEFAULT 0,
    processed_rows INTEGER DEFAULT 0,
    error TEXT,
    marketplace TEXT,
    domain TEXT,
    currency_code TEXT,
    currency_symbol TEXT,
    requested_rows INTEGER DEFAULT 0,
    quota_used INTEGER DEFAULT 0,
    quota_settled INTEGER DEFAULT 0
);
"""

_CREATE_QUOTA_TABLE = """
CREATE TABLE IF NOT EXISTS quota (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    daily_limit INTEGER NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    reserved INTEGER NOT NULL DEFAULT 0,
    quota_date TEXT NOT NULL,
    window_started_at TEXT,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute(_CREATE_JOBS_TABLE)
        conn.execute(_CREATE_QUOTA_TABLE)

        # Add new columns to jobs if they don't exist
        for col in ["requested_rows", "quota_used", "quota_settled"]:
            try:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        # Add reserved column to quota if not exists
        try:
            conn.execute("ALTER TABLE quota ADD COLUMN reserved INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # --- MIGRATION: Add window_started_at column ---
        # Check if column exists
        cursor = conn.execute("PRAGMA table_info(quota)")
        columns = [row[1] for row in cursor.fetchall()]
        if "window_started_at" not in columns:
            conn.execute("ALTER TABLE quota ADD COLUMN window_started_at TEXT")

        # --- MIGRATION: Populate window_started_at for existing rows ---
        # Prefer quota_date (fallback), then last_updated, then current time
        conn.execute("""
            UPDATE quota
            SET window_started_at = datetime(quota_date || 'T00:00:00')
            WHERE window_started_at IS NULL AND quota_date IS NOT NULL
        """)
        conn.execute("""
            UPDATE quota
            SET window_started_at = last_updated
            WHERE window_started_at IS NULL AND last_updated IS NOT NULL
        """)
        # Final fallback: current UTC time
        now_utc = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE quota SET window_started_at = ? WHERE window_started_at IS NULL",
            (now_utc,)
        )

        # Initialize quota if not exists
        from application.config import DAILY_QUOTA_LIMIT
        today = datetime.now(timezone.utc).date().isoformat()
        now_utc = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT OR IGNORE INTO quota (id, daily_limit, used, reserved, quota_date, window_started_at)
            VALUES (1, ?, 0, 0, ?, ?)
        """, (DAILY_QUOTA_LIMIT, today, now_utc))

        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
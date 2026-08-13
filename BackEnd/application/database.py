"""
database.py — SQLite setup using the Python standard-library sqlite3.

No ORM. A single `jobs` table tracks every scraping job.

Call `init_db()` once at application startup.
All other modules obtain a connection with `get_connection()`.
"""

import sqlite3
from contextlib import contextmanager
from application.config import DB_PATH

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id             TEXT PRIMARY KEY,
    status         TEXT NOT NULL DEFAULT 'created',
    created_at     TEXT NOT NULL,
    started_at     TEXT,
    completed_at   TEXT,
    input_file     TEXT,
    output_file    TEXT,
    total_rows     INTEGER DEFAULT 0,
    processed_rows INTEGER DEFAULT 0,
    error          TEXT
);
"""

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the database file and tables if they do not already exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(_CREATE_JOBS_TABLE)
        conn.commit()


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

@contextmanager
def get_connection():
    """
    Context manager that yields an open sqlite3.Connection and closes it
    automatically.  row_factory is set so rows are accessible like dicts.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

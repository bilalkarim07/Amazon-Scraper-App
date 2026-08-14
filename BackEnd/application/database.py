""" database.py — SQLite setup. """

import sqlite3
from contextlib import contextmanager
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
    error TEXT
    marketplace TEXT,
    domain TEXT,
    currency_code TEXT,
    currency_symbol TEXT
);
"""

def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(_CREATE_JOBS_TABLE)
        # Add new columns if they don't exist (SQLite doesn't support IF NOT EXISTS for columns)
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN marketplace TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN domain TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN currency_code TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN currency_symbol TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()

@contextmanager
def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
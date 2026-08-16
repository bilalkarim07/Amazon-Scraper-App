# BackEnd/application/files_database.py

""" files_database.py — SQLite setup for the files metadata database. """

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from application.storage import get_files_database_path

FILES_DB_PATH = get_files_database_path()

_CREATE_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    row_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'final',
    marketplace TEXT,
    currency_code TEXT,
    source_filename TEXT,
    file_size INTEGER DEFAULT 0,
    deleted_at TIMESTAMP
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_files_job_id ON files(job_id);",
    "CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_files_deleted_at ON files(deleted_at);",
    # Partial unique index to enforce uniqueness of filenames among active (non-deleted) files
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_files_active_filename ON files(filename) WHERE deleted_at IS NULL;",
]


def init_files_db() -> None:
    """Initialize the files database with schema and indexes."""
    FILES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_files_connection() as conn:
        conn.execute(_CREATE_FILES_TABLE)
        for index_sql in _CREATE_INDEXES:
            conn.execute(index_sql)
        conn.commit()


@contextmanager
def get_files_connection():
    """Context manager for files database connections."""
    conn = sqlite3.connect(str(FILES_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a dict."""
    return dict(row) if row else None
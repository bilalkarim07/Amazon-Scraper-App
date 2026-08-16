# BackEnd/application/files_database.py

import sqlite3
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/files.db")

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
    deleted_at TIMESTAMP,
    note TEXT   -- 👈 NEW COLUMN
);
"""

def get_files_connection():
    """Return a connection to the SQLite database."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_files_db():
    """Add the note column if it doesn't already exist."""
    with get_files_connection() as conn:
        try:
            conn.execute("ALTER TABLE files ADD COLUMN note TEXT")
            conn.commit()
            print("✅ Added 'note' column to files table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("ℹ️ 'note' column already exists, skipping migration")
            else:
                raise

def init_files_db():
    """Create the files table and run migrations."""
    with get_files_connection() as conn:
        conn.execute(_CREATE_FILES_TABLE)
        conn.commit()
    migrate_files_db()
"""Persistent directory tree backed by SQLite and Application_Directory storage."""
from __future__ import annotations

import sqlite3
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from application.storage import get_app_data_root

DIRECTORY_ROOT = get_app_data_root() / "Application_Directory"
DIRECTORY_DB = get_app_data_root() / "Database" / "directory.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS directory_nodes (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES directory_nodes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK(node_type IN ('folder', 'file', 'google_sheet')),
    storage_name TEXT,
    url TEXT,
    size INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(parent_id, name)
);
CREATE INDEX IF NOT EXISTS idx_directory_parent ON directory_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_directory_type ON directory_nodes(node_type);
"""

ROOT_ID = "root"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    DIRECTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DIRECTORY_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_directory_db() -> None:
    DIRECTORY_ROOT.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.executescript(CREATE_TABLE)
        now = _now()
        conn.execute(
            "INSERT OR IGNORE INTO directory_nodes "
            "(id,parent_id,name,node_type,created_at,updated_at) VALUES (?,?,?,?,?,?)",
            (ROOT_ID, None, "Files", "folder", now, now),
        )
        conn.commit()


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def list_children(parent_id: str = ROOT_ID) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM directory_nodes WHERE parent_id=? "
            "ORDER BY CASE node_type WHEN 'folder' THEN 0 ELSE 1 END, lower(name)",
            (parent_id,),
        ).fetchall()
    return [_row(r) for r in rows]


def get_node(node_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM directory_nodes WHERE id=?", (node_id,)).fetchone()
    return _row(row) if row else None


def _validate_name(name: str) -> str:
    value = name.strip()
    if not value or value in {".", ".."} or any(c in value for c in '\\/:*?"<>|'):
        raise ValueError("Invalid directory name")
    return value


def _ensure_parent(parent_id: str) -> None:
    parent = get_node(parent_id)
    if not parent or parent["node_type"] != "folder":
        raise ValueError("Parent directory does not exist")


def create_folder(parent_id: str, name: str) -> dict[str, Any]:
    _ensure_parent(parent_id)
    name = _validate_name(name)
    node_id = uuid.uuid4().hex
    now = _now()
    folder = DIRECTORY_ROOT / node_id
    folder.mkdir(parents=True, exist_ok=False)
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO directory_nodes(id,parent_id,name,node_type,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (node_id, parent_id, name, "folder", now, now),
            )
            conn.commit()
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return get_node(node_id)  # type: ignore[return-value]


def create_google_sheet(parent_id: str, name: str, url: str) -> dict[str, Any]:
    _ensure_parent(parent_id)
    name = _validate_name(name)
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.netloc != "docs.google.com" or not parsed.path.startswith("/spreadsheets/"):
        raise ValueError("A valid Google Sheets URL is required")
    node_id = uuid.uuid4().hex
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO directory_nodes(id,parent_id,name,node_type,url,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (node_id, parent_id, name, "google_sheet", url.strip(), now, now),
        )
        conn.commit()
    return get_node(node_id)  # type: ignore[return-value]


def register_file(parent_id: str, name: str, source: Path) -> dict[str, Any]:
    _ensure_parent(parent_id)
    name = _validate_name(name)
    if not source.is_file():
        raise FileNotFoundError("Source file does not exist")
    node_id = uuid.uuid4().hex
    storage_name = f"{node_id}{source.suffix}"
    destination = DIRECTORY_ROOT / storage_name
    shutil.copy2(source, destination)
    now = _now()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO directory_nodes(id,parent_id,name,node_type,storage_name,size,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (node_id, parent_id, name, "file", storage_name, destination.stat().st_size, now, now),
            )
            conn.commit()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return get_node(node_id)  # type: ignore[return-value]


def rename_node(node_id: str, name: str) -> dict[str, Any]:
    if node_id == ROOT_ID:
        raise ValueError("The root directory cannot be renamed")
    node = get_node(node_id)
    if not node:
        raise KeyError("Directory item not found")
    name = _validate_name(name)
    with get_connection() as conn:
        conn.execute("UPDATE directory_nodes SET name=?, updated_at=? WHERE id=?", (name, _now(), node_id))
        conn.commit()
    return get_node(node_id)  # type: ignore[return-value]


def delete_node(node_id: str) -> None:
    if node_id == ROOT_ID:
        raise ValueError("The root directory cannot be deleted")
    node = get_node(node_id)
    if not node:
        raise KeyError("Directory item not found")
    with get_connection() as conn:
        conn.execute("DELETE FROM directory_nodes WHERE id=?", (node_id,))
        conn.commit()
    if node["node_type"] == "folder":
        shutil.rmtree(DIRECTORY_ROOT / node_id, ignore_errors=True)
    elif node["node_type"] == "file" and node.get("storage_name"):
        (DIRECTORY_ROOT / node["storage_name"]).unlink(missing_ok=True)

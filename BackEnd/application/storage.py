# BackEnd/application/storage.py

import os
import shutil
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_app_data_root() -> Path:
    """Return OS‑appropriate application data root."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            userprofile = os.environ.get("USERPROFILE", "")
            base = os.path.join(userprofile, "AppData", "Local")
        return Path(base) / "AmazonListingScraper"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AmazonListingScraper"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            return Path(xdg) / "AmazonListingScraper"
        return Path.home() / ".local" / "share" / "AmazonListingScraper"


def get_database_path() -> Path:
    """Return the path to the main application database (app.db)."""
    return get_app_data_root() / "Database" / "app.db"


def get_files_database_path() -> Path:
    """Return the path to the files metadata database (files.db)."""
    return get_app_data_root() / "Database" / "files.db"


def get_files_dir() -> Path:
    """Return the directory for persistent output CSV files."""
    return get_app_data_root() / "Files"


def get_jobs_dir() -> Path:
    """Return the directory for job workspaces."""
    return get_app_data_root() / "Jobs"


def get_job_dir(job_id: str) -> Path:
    """Return the workspace directory for a specific job."""
    return get_jobs_dir() / job_id


def ensure_directories() -> None:
    """Create all required directories if they don't exist."""
    get_database_path().parent.mkdir(parents=True, exist_ok=True)
    get_files_database_path().parent.mkdir(parents=True, exist_ok=True)
    get_files_dir().mkdir(parents=True, exist_ok=True)
    get_jobs_dir().mkdir(parents=True, exist_ok=True)


def migrate_existing_data() -> bool:
    """
    One‑time migration from legacy project‑relative storage to centralised storage.

    Returns True if migration was performed, False otherwise.
    """
    # Legacy paths (relative to project root)
    base_dir = Path(__file__).resolve().parent.parent
    old_db = base_dir / "data" / "scraper.db"
    old_jobs = base_dir / "data" / "jobs"
    new_db = get_database_path()
    new_jobs = get_jobs_dir()

    # If new database already exists, do nothing
    if new_db.exists():
        return False

    # Check for old database or old job data
    has_old_data = old_db.exists() or old_jobs.exists()
    if not has_old_data:
        return False

    # Migrate database
    if old_db.exists():
        try:
            new_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_db, new_db)
            logger.info(f"Migrated database from {old_db} to {new_db}")
        except Exception as e:
            logger.error(f"Failed to migrate database: {e}")

    # Migrate job directories
    if old_jobs.exists():
        try:
            # Copy entire jobs tree, skipping existing files
            shutil.copytree(old_jobs, new_jobs, symlinks=True, dirs_exist_ok=True)
            logger.info(f"Migrated job directories from {old_jobs} to {new_jobs}")
        except Exception as e:
            logger.error(f"Failed to migrate job directories: {e}")

    return True
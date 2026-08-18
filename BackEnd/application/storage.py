# BackEnd/application/storage.py

import os
import shutil
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_app_data_root() -> Path:
    """Return OS-appropriate application data root."""
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
    return get_app_data_root() / "Database" / "app.db"


def get_files_database_path() -> Path:
    return get_app_data_root() / "Database" / "files.db"


def get_directory_database_path() -> Path:
    return get_app_data_root() / "Database" / "directory.db"


def get_files_dir() -> Path:
    return get_app_data_root() / "Files"


def get_application_directory() -> Path:
    return get_app_data_root() / "Application_Directory"


def get_jobs_dir() -> Path:
    return get_app_data_root() / "Jobs"


def get_job_dir(job_id: str) -> Path:
    return get_jobs_dir() / job_id


def ensure_directories() -> None:
    get_database_path().parent.mkdir(parents=True, exist_ok=True)
    get_files_database_path().parent.mkdir(parents=True, exist_ok=True)
    get_directory_database_path().parent.mkdir(parents=True, exist_ok=True)
    get_files_dir().mkdir(parents=True, exist_ok=True)
    get_application_directory().mkdir(parents=True, exist_ok=True)
    get_jobs_dir().mkdir(parents=True, exist_ok=True)


def migrate_existing_data() -> bool:
    """One-time migration from legacy project-relative storage to centralised storage."""
    base_dir = Path(__file__).resolve().parent.parent
    old_db = base_dir / "data" / "scraper.db"
    old_jobs = base_dir / "data" / "jobs"
    new_db = get_database_path()
    new_jobs = get_jobs_dir()

    if new_db.exists():
        return False

    has_old_data = old_db.exists() or old_jobs.exists()
    if not has_old_data:
        return False

    if old_db.exists():
        try:
            new_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_db, new_db)
            logger.info(f"Migrated database from {old_db} to {new_db}")
        except Exception as e:
            logger.error(f"Failed to migrate database: {e}")

    if old_jobs.exists():
        try:
            shutil.copytree(old_jobs, new_jobs, symlinks=True, dirs_exist_ok=True)
            logger.info(f"Migrated job directories from {old_jobs} to {new_jobs}")
        except Exception as e:
            logger.error(f"Failed to migrate job directories: {e}")

    return True

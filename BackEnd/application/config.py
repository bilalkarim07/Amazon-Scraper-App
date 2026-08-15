""" config.py — Application configuration with environment awareness. """

import os
from pathlib import Path

from application.storage import get_app_data_root, get_jobs_dir

# --- Use centralized storage ---
APP_DATA_ROOT = get_app_data_root()
DATA_DIR = APP_DATA_ROOT / "Database"   # Kept for backward compatibility
JOBS_DIR = get_jobs_dir()               # Override to use centralized storage
DB_PATH = APP_DATA_ROOT / "Database" / "app.db"

# --- Engine paths (these remain relative to the project for now) ---
BASE_DIR = Path(__file__).resolve().parent.parent
ENGINE_ROOT = BASE_DIR.parent / "ScraperEngine"
ENGINE_RUNNER = ENGINE_ROOT / "application_runner.py"

# --- Python executable ---
UV_EXECUTABLE = os.environ.get("UV", "uv")

# --- Headless mode ---
HEADLESS_MODE = 'false'

# --- Wait defaults (seconds) ---
DEFAULT_FIRST_PAGE_WAIT = 150
DEFAULT_NEXT_PAGE_WAIT = 5

# --- CORS origins ---
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# --- Quota ---
DAILY_QUOTA_LIMIT = int(os.environ.get("DAILY_QUOTA_LIMIT", 2000))
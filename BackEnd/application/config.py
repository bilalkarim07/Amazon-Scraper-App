""" config.py — Application configuration with environment awareness. """

import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
JOBS_DIR = DATA_DIR / "jobs"
DB_PATH = DATA_DIR / "scraper.db"

# --- Engine paths ---
ENGINE_ROOT = BASE_DIR.parent / "ScraperEngine"
ENGINE_RUNNER = ENGINE_ROOT / "application_runner.py"

# --- Python executable ---
UV_EXECUTABLE = os.environ.get("UV", "uv")

# --- Headless mode ---
# Default to False for development, override with env var for production.
HEADLESS_MODE = 'false'

# --- Wait defaults (seconds) ---
DEFAULT_FIRST_PAGE_WAIT = 150
DEFAULT_NEXT_PAGE_WAIT = 5

# --- Ensure directories exist ---
DATA_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# TanStack dev server runs on 3000; add 3001 as fallback
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]



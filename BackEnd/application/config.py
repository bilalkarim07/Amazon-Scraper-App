"""
config.py — Centralised configuration for the BackEnd application.

All paths and constants live here so nothing is hard-coded in service files.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------

# Root of the BackEnd project (contains this `application/` package)
BACKEND_ROOT: Path = Path(__file__).resolve().parent.parent

# Root of the ScraperEngine project (sibling directory)
ENGINE_ROOT: Path = BACKEND_ROOT.parent / "ScraperEngine"

# Where all job data is stored: BackEnd/data/jobs/<job_id>/
DATA_DIR: Path = BACKEND_ROOT / "data"
JOBS_DIR: Path = DATA_DIR / "jobs"

# SQLite database file
DB_PATH: Path = DATA_DIR / "jobs.db"

# ---------------------------------------------------------------------------
# Engine invocation
# ---------------------------------------------------------------------------

# The `uv` executable inside the ScraperEngine venv.
# On Windows, uv is typically on PATH after installation; we rely on that.
# If not on PATH, set UV_EXECUTABLE env var to the full path.
UV_EXECUTABLE: str = os.environ.get("UV_EXECUTABLE", "uv")

# Path to the thin CLI runner script inside the engine project
ENGINE_RUNNER: Path = ENGINE_ROOT / "application_runner.py"

# ---------------------------------------------------------------------------
# CORS — origins allowed to call the API
# ---------------------------------------------------------------------------

# TanStack dev server runs on 3000; add 3001 as fallback
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# ---------------------------------------------------------------------------
# Job defaults
# ---------------------------------------------------------------------------

DEFAULT_FIRST_PAGE_WAIT: int = 150   # seconds
DEFAULT_NEXT_PAGE_WAIT: int = 5      # seconds

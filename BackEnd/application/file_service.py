"""
file_service.py — Helpers for resolving and validating job output files.

The FastAPI download route delegates to this module so it has no knowledge
of the filesystem layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import logging

from application import job_service
from application.storage import get_app_data_root

logger = logging.getLogger(__name__)


def get_output_path(job_id: str) -> Optional[Path]:
    """
    Return the Path to the job's output CSV, or None if:
      - the job doesn't exist
      - the job is not yet completed
      - the output file is missing from disk

    Supports both absolute paths (legacy) and paths relative to the
    application data root (new centralized storage).
    """
    job = job_service.get_job(job_id)
    if not job:
        return None

    output_file = job.get("output_file")
    if not output_file:
        return None

    path = Path(output_file)

    # If the path is already absolute, use it as-is
    if path.is_absolute():
        if path.is_file():
            return path
        logger.warning("Absolute output file missing: %s", path)
        return None

    # Otherwise, resolve relative to the application data root
    app_root = get_app_data_root()
    resolved_path = app_root / output_file
    if resolved_path.is_file():
        return resolved_path

    logger.warning("Output file not found at resolved path: %s", resolved_path)
    return None
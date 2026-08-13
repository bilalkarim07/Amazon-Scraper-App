"""
file_service.py — Helpers for resolving and validating job output files.

The FastAPI download route delegates to this module so it has no knowledge
of the filesystem layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from application.config import JOBS_DIR
from application import job_service


def get_output_path(job_id: str) -> Optional[Path]:
    """
    Return the Path to the job's output CSV, or None if:
      - the job doesn't exist
      - the job is not yet completed
      - the output file is missing from disk
    """
    job = job_service.get_job(job_id)
    if not job:
        return None

    output_file = job.get("output_file")
    if not output_file:
        return None

    path = Path(output_file)
    return path if path.is_file() else None

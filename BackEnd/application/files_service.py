# BackEnd/application/files_service.py

""" files_service.py — Persistent file metadata service using files.db. """

from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
import os

from application.files_database import get_files_connection
from application.storage import get_app_data_root, get_files_dir
from application import job_service

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a dict."""
    return dict(row) if row else None


def sanitize_filename(base_name: str) -> str:
    """
    Sanitize and normalize a user-provided output filename.

    The filename remains exactly the user's requested name apart from
    unsafe characters and the .csv extension.

    Example:
        "my_data.csv" -> "my_data.csv"
        "test scraped.csv" -> "test_scraped.csv"
        "results" -> "results.csv"
    """
    # Remove any directory/path components.
    base_name = os.path.basename(base_name.strip())

    # Sanitize: keep alphanumerics, underscore, dash and dot.
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", base_name)

    if not sanitized:
        sanitized = "output"

    # Ensure .csv extension.
    if not sanitized.lower().endswith(".csv"):
        sanitized += ".csv"

    return sanitized


def resolve_unique_filename(base_name: str) -> str:
    """
    Return the lowest available filename that does not collide with an active
    (non‑deleted) file in files.db.

    Examples:
        existing: output.csv          → returns output.csv
        existing: output.csv          → returns output_1.csv
        existing: output.csv, output_1.csv → returns output_2.csv
        existing: output.csv, output_1.csv, output_3.csv → returns output_2.csv
    Soft‑deleted files are ignored.
    """
    sanitized = sanitize_filename(base_name)
    name, ext = os.path.splitext(sanitized)

    with get_files_connection() as conn:
        # Query all active filenames that start with the same base name and have the same extension
        pattern = f"{name}%{ext}"
        rows = conn.execute(
            "SELECT filename FROM files WHERE deleted_at IS NULL AND filename LIKE ?",
            (pattern,)
        ).fetchall()

    existing = {row["filename"] for row in rows}

    # If the exact name is free, use it
    if sanitized not in existing:
        return sanitized

    # Otherwise find the lowest suffix _N
    suffix = 1
    while True:
        candidate = f"{name}_{suffix}{ext}"
        if candidate not in existing:
            return candidate
        suffix += 1


def create_file_record(
    job_id: str,
    source_path: Path,
    base_name: Optional[str] = None,
    status: str = "final",
    marketplace: Optional[str] = None,
    currency_code: Optional[str] = None,
    source_filename: Optional[str] = None,
    row_count: int = 0,
) -> Optional[Dict[str, Any]]:
    """
    Copy a file from the job workspace to the Files directory and create a metadata record.

    Args:
        job_id: The ID of the job that generated the file
        source_path: Path to the source file in the job workspace
        base_name: Optional user‑provided base filename (used to generate a unique name)
        status: 'final' or 'partial'
        marketplace: Marketplace identifier
        currency_code: Currency code
        source_filename: Original uploaded filename
        row_count: Number of data rows in the CSV

    Returns:
        The created file record as a dict, or None if failed
    """
    if not source_path.exists() or not source_path.is_file():
        logger.error(f"Source file does not exist: {source_path}")
        return None

    # Use base_name if provided, else fallback to source_path.name
    if base_name is None:
        base_name = source_path.name

    files_dir = get_files_dir()
    files_dir.mkdir(parents=True, exist_ok=True)

    # Retry loop for concurrent insert conflicts
    max_retries = 3
    for attempt in range(max_retries):
        # Determine the final unique filename
        unique_filename = resolve_unique_filename(base_name)
        dest_path = files_dir / unique_filename

        # Copy the file (not move, to preserve job workspace for debugging)
        try:
            shutil.copy2(source_path, dest_path)
            file_size = dest_path.stat().st_size
        except Exception as e:
            logger.error(f"Failed to copy file to Files directory: {e}")
            return None

        # Store path relative to app data root
        app_root = get_app_data_root()
        try:
            relative_path = str(dest_path.relative_to(app_root))
        except ValueError:
            relative_path = str(dest_path)

        # Create database record
        now = _now_iso()
        try:
            with get_files_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO files (
                        job_id, filename, path, created_at, updated_at,
                        row_count, status, marketplace, currency_code,
                        source_filename, file_size
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        unique_filename,          # Display name
                        relative_path,            # Physical path
                        now,
                        now,
                        row_count,
                        status,
                        marketplace,
                        currency_code,
                        source_filename,
                        file_size,
                    ),
                )
                conn.commit()
                file_id = cursor.lastrowid
            # Return the created record
            return get_file(file_id)
        except sqlite3.IntegrityError as e:
            # Unique index violation – another job took the same name; retry
            if attempt == max_retries - 1:
                logger.error(f"Failed to allocate a unique filename after {max_retries} attempts: {e}")
                raise RuntimeError(f"Failed to allocate a unique filename after {max_retries} attempts") from e
            # Remove the copied file (we'll copy again to a new name)
            if dest_path.exists():
                try:
                    dest_path.unlink()
                except OSError:
                    pass
            # Continue to next retry; resolve_unique_filename will be called again

    return None


def get_file(file_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a file record by ID."""
    with get_files_connection() as conn:
        row = conn.execute(
            "SELECT * FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
        return _row_to_dict(row)


def list_files(include_deleted: bool = False) -> List[Dict[str, Any]]:
    """
    List all files, optionally including soft-deleted ones.

    Returns files ordered by created_at descending (newest first).
    """
    with get_files_connection() as conn:
        if include_deleted:
            rows = conn.execute(
                "SELECT * FROM files ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM files WHERE deleted_at IS NULL ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_dict(row) for row in rows]


def list_files_by_job(job_id: str) -> List[Dict[str, Any]]:
    """List all files associated with a specific job."""
    with get_files_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM files WHERE job_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
            (job_id,),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]


def resolve_file_path(file_record: Dict[str, Any]) -> Optional[Path]:
    """
    Resolve a file record's stored path to an absolute Path.

    The path is stored relative to the application data root.
    """
    path_str = file_record.get("path")
    if not path_str:
        return None

    path = Path(path_str)
    if path.is_absolute():
        return path if path.exists() else None

    # Resolve relative to app data root
    app_root = get_app_data_root()
    resolved = app_root / path_str
    return resolved if resolved.exists() else None


def update_file(file_id: int, **fields) -> Optional[Dict[str, Any]]:
    """
    Update a file record.

    Supported fields: filename, marketplace, currency_code, source_filename, row_count, status
    """
    if not fields:
        return get_file(file_id)

    # Validate and sanitize filename if provided
    if "filename" in fields:
        new_filename = sanitize_filename(fields["filename"])

        # Check if this new filename is already in use by another active file (excluding self)
        file_record = get_file(file_id)
        if not file_record:
            raise ValueError(f"File with id {file_id} not found")

        with get_files_connection() as conn:
            conflict = conn.execute(
                "SELECT id FROM files WHERE deleted_at IS NULL AND filename = ? AND id != ?",
                (new_filename, file_id)
            ).fetchone()
            if conflict:
                raise ValueError(f"Filename '{new_filename}' is already in use by another active file")

        # Rename the physical file
        old_path = resolve_file_path(file_record)
        if old_path and old_path.exists():
            new_path = old_path.parent / new_filename
            try:
                old_path.rename(new_path)
                # Update the path field to reflect the new filename
                app_root = get_app_data_root()
                try:
                    fields["path"] = str(new_path.relative_to(app_root))
                except ValueError:
                    fields["path"] = str(new_path)
            except Exception as e:
                logger.error(f"Failed to rename physical file: {e}")
                raise ValueError(f"Could not rename physical file: {e}") from e
        else:
            logger.warning(f"Physical file for record {file_id} not found; updating record only")

        fields["filename"] = new_filename

    # Update the database
    fields["updated_at"] = _now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [file_id]

    with get_files_connection() as conn:
        conn.execute(
            f"UPDATE files SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()

    return get_file(file_id)


def delete_file(file_id: int, remove_physical: bool = True) -> bool:
    """
    Soft-delete a file.

    If remove_physical is True, the physical CSV file is also deleted.
    """
    file_record = get_file(file_id)
    if not file_record:
        return False

    # Remove physical file if requested
    if remove_physical:
        file_path = resolve_file_path(file_record)
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Deleted physical file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete physical file: {e}")
                # Continue with soft-delete even if physical deletion fails

    # Soft-delete the database record
    now = _now_iso()
    with get_files_connection() as conn:
        conn.execute(
            "UPDATE files SET deleted_at = ? WHERE id = ?",
            (now, file_id),
        )
        conn.commit()

    return True


def finalize_job_output(
    job_id: str,
    job_dir: Path,
    output_filename: str = "output.csv",
    status: str = "final",
    row_count: Optional[int] = None,
    base_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Finalize a job's output by copying it to the Files directory and creating a record.

    This is the main function called by scraper_service after job completion.

    Args:
        job_id: The job ID
        job_dir: The job workspace directory
        output_filename: The name of the output file in the job workspace
        status: 'final' or 'partial'
        row_count: Optional row count (will be counted if not provided)
        base_name: Optional user‑provided base name for the file (used to generate unique name)

    Returns:
        The created file record, or None if no output file exists
    """
    source_path = job_dir / output_filename
    if not source_path.exists() or not source_path.is_file():
        logger.warning(f"No output file found at {source_path}")
        return None

    # Get job metadata for the file record
    job = job_service.get_job(job_id)
    if job:
        marketplace = job.get("marketplace")
        currency_code = job.get("currency_code")
        source_filename = job.get("input_file")
    else:
        marketplace = None
        currency_code = None
        source_filename = None

    # Count rows if not provided
    if row_count is None:
        try:
            import csv
            with open(source_path, "r", encoding="utf-8") as f:
                row_count = max(0, sum(1 for _ in csv.reader(f)) - 1)
        except Exception:
            row_count = 0

    # Use the base name if provided, else fallback to the filename in the workspace
    if base_name is None:
        base_name = output_filename

    # Create the file record
    return create_file_record(
        job_id=job_id,
        source_path=source_path,
        base_name=base_name,
        status=status,
        marketplace=marketplace,
        currency_code=currency_code,
        source_filename=source_filename or source_path.name,
        row_count=row_count,
    )
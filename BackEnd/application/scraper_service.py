"""
scraper_service.py — Orchestrates the full lifecycle of a scraping job.

Responsibilities:
1. Create the job workspace on disk.
2. Normalise the uploaded CSV (rename the frontend column → 'Product Link').
3. Save the normalised input.csv.
4. Launch ScraperEngine/application_runner.py as a subprocess (non-blocking).
5. Monitor the subprocess in a background thread.
6. Update job status via job_service.

The FastAPI route should never touch AmazonScraper directly — all engine
communication goes through this module.
"""

from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from application import config
from application import job_service


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def start_job(
    job_id: str,
    csv_bytes: bytes,
    column_name: str,
    threads: int,
    first_page_wait: int,
    next_page_wait: int,
    output_filename: str,
    keywords: Optional[list[str]] = None,
    headless: bool = True,
) -> None:
    """
    Prepare the job workspace and launch the scraper in a background thread.

    This function returns immediately — the caller (FastAPI route) should NOT
    await it.  The background thread updates job status when it finishes.
    """
    job_dir = config.JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Normalise + save the input CSV ---
    try:
        total_rows, input_csv_path = _save_normalised_csv(
            csv_bytes=csv_bytes,
            column_name=column_name,
            job_dir=job_dir,
        )
    except ValueError as exc:
        job_service.mark_failed(job_id, str(exc))
        return

    # Update total_rows now that we know it
    job_service.update_job(job_id, total_rows=total_rows)

    # --- 2. Determine output path ---
    output_csv_path = job_dir / output_filename

    # --- 3. Launch subprocess in background thread ---
    bg = threading.Thread(
        target=_run_engine,
        args=(
            job_id,
            job_dir,
            input_csv_path,
            output_csv_path,
            threads,
            first_page_wait,
            next_page_wait,
            keywords or [],
            headless,
        ),
        daemon=True,   # Die with the main process if it exits
        name=f"scraper-{job_id[:8]}",
    )
    bg.start()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _save_normalised_csv(
    csv_bytes: bytes,
    column_name: str,
    job_dir: Path,
) -> tuple[int, Path]:
    """
    Read the uploaded CSV, validate that `column_name` exists, rename it to
    'Product Link', and write input.csv into the job directory.

    Returns (total_rows, path_to_input_csv).
    Raises ValueError with a human-readable message on validation failure.
    """
    text = csv_bytes.decode("utf-8-sig")   # strip BOM if present
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None or column_name not in reader.fieldnames:
        available = list(reader.fieldnames or [])
        raise ValueError(
            f"Column '{column_name}' not found in uploaded CSV. "
            f"Available columns: {available}"
        )

    # Rename the column and collect all rows
    rows = []
    for row in reader:
        # Rename frontend column → engine contract
        row["Product Link"] = row.pop(column_name)
        rows.append(row)

    if not rows:
        raise ValueError("Uploaded CSV contains no data rows.")

    # Build new fieldnames with 'Product Link' in place of the original column
    new_fieldnames = [
        "Product Link" if f == column_name else f
        for f in reader.fieldnames
    ]

    # Write normalised CSV
    input_csv_path = job_dir / "input.csv"
    with open(input_csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=new_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows), input_csv_path


def _run_engine(
    job_id: str,
    job_dir: Path,
    input_csv_path: Path,
    output_csv_path: Path,
    threads: int,
    first_page_wait: int,
    next_page_wait: int,
    keywords: list[str],
    headless: bool,
) -> None:
    """
    Run the ScraperEngine subprocess and update job status when it finishes.
    Executed inside a daemon background thread.
    """
    job_service.mark_running(job_id)

    cmd = [
        config.UV_EXECUTABLE,
        "run",
        "python",
        str(config.ENGINE_RUNNER),
        "--job-id",          job_id,
        "--job-dir",         str(job_dir),
        "--input-csv",       str(input_csv_path),
        "--output-csv",      str(output_csv_path),
        "--threads",         str(threads),
        "--first-page-wait", str(first_page_wait),
        "--next-page-wait",  str(next_page_wait),
    ]

    if keywords:
        cmd += ["--keywords", ",".join(keywords)]

    if headless:
        cmd.append("--headless")

    log_path = job_dir / "runner.log"

    try:
        with open(log_path, "w", encoding="utf-8") as log_fh:
            proc = subprocess.Popen(
                cmd,
                cwd=str(config.ENGINE_ROOT),   # engine's working directory
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                text=True,
            )
            proc.wait()

        if proc.returncode == 0 and output_csv_path.is_file():
            # Count output rows for the status response
            processed_rows = _count_csv_rows(output_csv_path)
            job_service.mark_completed(
                job_id,
                output_file=str(output_csv_path),
                processed_rows=processed_rows,
            )
        else:
            # Grab last few lines from log for the error field
            error_snippet = _tail_log(log_path, lines=20)
            job_service.mark_failed(
                job_id,
                error=f"Runner exited with code {proc.returncode}.\n{error_snippet}",
            )

    except Exception as exc:
        job_service.mark_failed(job_id, error=str(exc))


def _count_csv_rows(path: Path) -> int:
    """Count data rows (excluding header) in a CSV file."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            total_rows = sum(1 for _ in reader)
            return max(0, total_rows - 1)
    except Exception:
        return 0


def _tail_log(path: Path, lines: int = 20) -> str:
    """Return the last N lines from a text file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()
        return "".join(all_lines[-lines:])
    except Exception:
        return ""

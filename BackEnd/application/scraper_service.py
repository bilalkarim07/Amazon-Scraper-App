""" scraper_service.py — Orchestrates the full lifecycle of a scraping job. """

from __future__ import annotations
import csv
import io
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from application import config
from application import job_service

# --- Global registry of running subprocesses ---
_running_processes: Dict[str, subprocess.Popen] = {}
_process_lock = threading.Lock()


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
    """Prepare the job workspace and launch the scraper in a background thread."""
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
        daemon=True,
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
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None or column_name not in reader.fieldnames:
        available = list(reader.fieldnames or [])
        raise ValueError(
            f"Column '{column_name}' not found in uploaded CSV. "
            f"Available columns: {available}"
        )

    rows = []
    for row in reader:
        row["Product Link"] = row.pop(column_name)
        rows.append(row)

    if not rows:
        raise ValueError("Uploaded CSV contains no data rows.")

    new_fieldnames = [
        "Product Link" if f == column_name else f
        for f in reader.fieldnames
    ]

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
    """Run the ScraperEngine subprocess and update job status."""
    job_service.mark_running(job_id)

    cmd = [
        config.UV_EXECUTABLE,
        "run",
        "python",
        str(config.ENGINE_RUNNER),
        "--job-id", job_id,
        "--job-dir", str(job_dir),
        "--input-csv", str(input_csv_path),
        "--output-csv", str(output_csv_path),
        "--threads", str(threads),
        "--first-page-wait", str(first_page_wait),
        "--next-page-wait", str(next_page_wait),
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
                cwd=str(config.ENGINE_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Register process for cancellation
            with _process_lock:
                _running_processes[job_id] = proc

            # Read stdout line by line — parse JSON progress events
            try:
                for line in iter(proc.stdout.readline, ""):
                    if not line:
                        break
                    # Always write to runner.log
                    log_fh.write(line)
                    log_fh.flush()

                    # Try to parse as JSON progress event
                    line_stripped = line.strip()
                    if line_stripped.startswith("{") and line_stripped.endswith("}"):
                        try:
                            event = json.loads(line_stripped)
                            if event.get("event") == "progress":
                                processed = event.get("processed", 0)
                                total = event.get("total", 0)
                                job_service.update_progress(job_id, processed)
                                # Also update total_rows if not set
                                if total > 0:
                                    current = job_service.get_job(job_id)
                                    if current and current.get("total_rows", 0) == 0:
                                        job_service.update_job(job_id, total_rows=total)
                            elif event.get("event") == "completed":
                                processed = event.get("processed", 0)
                                # Final progress update
                                job_service.update_progress(job_id, processed)
                            elif event.get("event") == "failed":
                                error_msg = event.get("error", "Unknown engine error")
                                job_service.mark_failed(job_id, error_msg)
                        except json.JSONDecodeError:
                            pass  # Not a JSON line, continue

            finally:
                proc.stdout.close()

            # Wait for process to exit
            return_code = proc.wait()

            # Unregister process
            with _process_lock:
                _running_processes.pop(job_id, None)

            # Final status update based on return code
            if return_code == 0 and output_csv_path.is_file():
                processed_rows = _count_csv_rows(output_csv_path)
                job_service.mark_completed(
                    job_id,
                    output_file=str(output_csv_path),
                    processed_rows=processed_rows,
                )
            else:
                # Check if job was cancelled
                job = job_service.get_job(job_id)
                if job and job.get("status") == "cancelling":
                    # Already marked cancelling; ensure it's cancelled
                    processed_rows = _count_csv_rows(output_csv_path) if output_csv_path.is_file() else 0
                    job_service.mark_cancelled(job_id, processed_rows)
                else:
                    error_snippet = _tail_log(log_path, lines=20)
                    job_service.mark_failed(
                        job_id,
                        error=f"Runner exited with code {return_code}.\n{error_snippet}",
                    )

    except Exception as exc:
        with _process_lock:
            _running_processes.pop(job_id, None)
        job_service.mark_failed(job_id, str(exc))


def cancel_job(job_id: str) -> bool:
    """
    Request cancellation of a running job.
    Creates a .cancel flag file and terminates the subprocess.
    Returns True if the job was successfully marked as cancelled.
    """
    job = job_service.get_job(job_id)
    if not job:
        return False

    # Only running or created jobs can be cancelled
    if job.get("status") not in ("running", "created"):
        return False

    # Mark as cancelling in database
    job_service.mark_cancelling(job_id)

    # Create the .cancel flag file so the engine can detect cancellation cooperatively
    job_dir = config.JOBS_DIR / job_id
    cancel_file = job_dir / ".cancel"
    try:
        cancel_file.touch()
    except Exception as e:
        # If we can't create the file, log but continue (subprocess termination will still occur)
        import logging
        logging.warning(f"Could not create .cancel file for job {job_id}: {e}")

    # Get the subprocess and terminate it
    with _process_lock:
        proc = _running_processes.get(job_id)

    if proc:
        try:
            # Send SIGTERM (works on Windows via terminate())
            proc.terminate()
            # Wait up to 10 seconds for the process to exit cleanly
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't respond
                proc.kill()
                proc.wait()
        except Exception as e:
            import logging
            logging.warning(f"Error terminating subprocess for job {job_id}: {e}")

    # Mark as cancelled (processed_rows will be updated by the engine or we'll count what exists)
    output_file = job.get("output_file")
    processed_rows = 0
    if output_file and Path(output_file).is_file():
        processed_rows = _count_csv_rows(Path(output_file))

    job_service.mark_cancelled(job_id, processed_rows)
    return True


def _count_csv_rows(path: Path) -> int:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            total_rows = sum(1 for _ in reader)
            return max(0, total_rows - 1)
    except Exception:
        return 0


def _tail_log(path: Path, lines: int = 20) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            all_lines = fh.readlines()
            return "".join(all_lines[-lines:])
    except Exception:
        return ""
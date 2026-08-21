""" scraper_service.py — Orchestrates the full lifecycle of a scraping job. """

from __future__ import annotations
import csv
import io
import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict

from application import config
from application import job_service
from application import quota_service
from application import files_service
from application.storage import get_app_data_root, get_jobs_dir

_running_processes: Dict[str, subprocess.Popen] = {}
_process_lock = threading.Lock()


def _get_base_url(marketplace: str) -> str:
    from application.marketplace_config import get_marketplace
    cfg = get_marketplace(marketplace)
    if cfg:
        return cfg.get("base_url", "https://www.amazon.com/")
    return "https://www.amazon.com/"


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
    marketplace: str = "US",
    currency_code: str = "USD",
    currency_symbol: str = "$",
) -> None:
    """Prepare the job workspace and launch the scraper in a background thread."""
    # Use centralized Jobs directory
    jobs_root = get_jobs_dir()
    job_dir = jobs_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

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
    output_csv_path = job_dir / output_filename

    bg = threading.Thread(
        target=_run_engine,
        args=(
            job_id, job_dir, input_csv_path, output_csv_path,
            threads, first_page_wait, next_page_wait, keywords or [], headless,
            marketplace, currency_code, currency_symbol,
        ),
        daemon=True,
        name=f"scraper-{job_id[:8]}",
    )
    bg.start()


def _save_normalised_csv(csv_bytes: bytes, column_name: str, job_dir: Path) -> tuple[int, Path]:
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or column_name not in reader.fieldnames:
        available = list(reader.fieldnames or [])
        raise ValueError(f"Column '{column_name}' not found. Available: {available}")
    rows = []
    for row in reader:
        row["Product Link"] = row.pop(column_name)
        rows.append(row)
    if not rows:
        raise ValueError("Uploaded CSV contains no data rows.")
    new_fieldnames = ["Product Link" if f == column_name else f for f in reader.fieldnames]
    input_csv_path = job_dir / "input.csv"
    with open(input_csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=new_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows), input_csv_path


def _count_csv_rows(path: Path) -> int:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return max(0, sum(1 for _ in csv.reader(fh)) - 1)
    except Exception:
        return 0


def _tail_log(path: Path, lines: int = 20) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-lines:])
    except Exception:
        return ""


# --- Helpers for cancellation and partial-result counting ---

def _count_successful_rows_from_threads(job_dir: Path) -> int:
    """Count successfully scraped rows from thread CSV files in the workspace."""
    workspace_dir = job_dir / "workspace"
    if not workspace_dir.exists():
        return 0
    total = 0
    for thread_file in workspace_dir.glob("thread_*.csv"):
        try:
            with open(thread_file, "r", encoding="utf-8") as fh:
                # Subtract 1 for header row
                total += max(0, sum(1 for _ in csv.reader(fh)) - 1)
        except Exception:
            continue
    return total


def _is_cancelled(job_dir: Path) -> bool:
    """Check if the .cancel flag file exists."""
    return (job_dir / ".cancel").exists()


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
    marketplace: str,
    currency_code: str,
    currency_symbol: str,
) -> None:
    """
    Run the ScraperEngine subprocess, then settle quota based on successful rows.
    Quota is reconciled using the number of valid successful rows (excluding timeouts and failures).
    """
    job_service.mark_running(job_id)

    cmd = [
        config.UV_EXECUTABLE, "run", "python", str(config.ENGINE_RUNNER),
        "--job-id", job_id,
        "--job-dir", str(job_dir),
        "--input-csv", str(input_csv_path),
        "--output-csv", str(output_csv_path),
        "--threads", str(threads),
        "--first-page-wait", str(first_page_wait),
        "--next-page-wait", str(next_page_wait),
        "--marketplace", marketplace,
        "--base-url", _get_base_url(marketplace),
        "--currency-code", currency_code,
        "--currency-symbol", currency_symbol,
    ]
    if keywords:
        cmd += ["--keywords", ",".join(keywords)]
    if headless:
        cmd.append("--headless")

    log_path = job_dir / "runner.log"
    successful_rows = 0
    requested_rows = 0

    try:
        with open(log_path, "w", encoding="utf-8") as log_fh:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            proc = subprocess.Popen(
                cmd,
                cwd=str(config.ENGINE_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )

            with _process_lock:
                _running_processes[job_id] = proc

            # Read output line by line to parse progress events
            try:
                for line in iter(proc.stdout.readline, ""):
                    if not line:
                        break
                    log_fh.write(line)
                    log_fh.flush()

                    line_stripped = line.strip()
                    if line_stripped.startswith("{") and line_stripped.endswith("}"):
                        try:
                            event = json.loads(line_stripped)
                            if event.get("event") == "progress":
                                processed = event.get("processed", 0)
                                total = event.get("total", 0)
                                job_service.update_progress(job_id, processed)
                                if total > 0:
                                    current = job_service.get_job(job_id)
                                    if current and current.get("total_rows", 0) == 0:
                                        job_service.update_job(job_id, total_rows=total)
                            elif event.get("event") == "completed":
                                # Extract success count (timeouts and failures are excluded)
                                successful_rows = event.get("successful", 0)
                                # Optional: also capture timeout/failure counts for logging
                                timeout_count = event.get("timeout", 0)
                                failure_count = event.get("failure", 0)
                                logging.info(
                                    f"Engine completed: success={successful_rows}, "
                                    f"timeout={timeout_count}, failure={failure_count}"
                                )
                                processed = event.get("processed", 0)
                                job_service.update_progress(job_id, processed)
                            elif event.get("event") == "failed":
                                error_msg = event.get("error", "Unknown engine error")
                                job_service.mark_failed(job_id, error_msg)
                        except json.JSONDecodeError:
                            pass

            finally:
                proc.stdout.close()

            return_code = proc.wait()

            with _process_lock:
                _running_processes.pop(job_id, None)

            # Determine processed rows for display
            processed_rows = _count_csv_rows(output_csv_path) if output_csv_path.is_file() else 0

            # Get requested rows from job record
            job = job_service.get_job(job_id)
            requested_rows = job.get("requested_rows", 0) if job else 0

            # --- Check if cancellation was requested ---
            cancellation_requested = _is_cancelled(job_dir)

            # --- If no "completed" event was received, fall back to counting thread files ---
            if successful_rows == 0 and not cancellation_requested:
                successful_rows = _count_successful_rows_from_threads(job_dir)

            # --- Handle cancellation ---
            if cancellation_requested:
                # Count actual successful rows from thread CSVs (more reliable than progress events)
                actual_successful = _count_successful_rows_from_threads(job_dir)
                if actual_successful > 0:
                    successful_rows = actual_successful
                # If we have a partial output file, use its row count too (paranoid fallback)
                if output_csv_path.is_file() and successful_rows == 0:
                    successful_rows = _count_csv_rows(output_csv_path)

                # --- Finalize partial output to Files/ (with user‑provided base name) ---
                if output_csv_path.is_file() and successful_rows > 0:
                    file_record = files_service.finalize_job_output(
                        job_id=job_id,
                        job_dir=job_dir,
                        output_filename=output_csv_path.name,
                        status="partial",
                        row_count=successful_rows,
                        base_name=output_csv_path.name,
                    )
                    if file_record:
                        app_root = get_app_data_root()
                        try:
                            relative_output = str(Path(file_record["path"]))
                        except Exception:
                            relative_output = file_record["path"]
                        job_service.update_job(job_id, output_file=relative_output)

                # --- Settle quota for cancelled job ---
                if requested_rows > 0:
                    try:
                        # This releases unused reserved quota and updates quota_used
                        quota_service.settle_quota(job_id, requested_rows, successful_rows)
                    except Exception as exc:
                        logging.error(f"Quota settlement failed for cancelled job {job_id}: {exc}")

                job_service.mark_cancelled(job_id, successful_rows)
                return

            # --- Normal completion path ---
            # --- SETTLE QUOTA (idempotent) with error handling ---
            # quota_service.settle_quota handles releasing unused reserved quota
            # and updating the job's quota_used and quota_settled fields.
            quota_failed = False
            quota_error = None
            if requested_rows > 0:
                try:
                    quota_service.settle_quota(job_id, requested_rows, successful_rows)
                except Exception as exc:
                    quota_failed = True
                    quota_error = str(exc)
                    logging.error(f"Quota settlement failed for job {job_id}: {exc}")

            # --- Update job status ---
            if return_code == 0 and output_csv_path.is_file():
                if quota_failed:
                    # Scraping succeeded but quota finalization failed.
                    # Preserve the output CSV but mark job as failed with clear error.
                    job_service.mark_failed(
                        job_id,
                        error=f"Scraping succeeded but quota finalization failed: {quota_error}",
                    )
                else:
                    # --- FINALIZE OUTPUT TO FILES DIRECTORY (with user‑provided base name) ---
                    file_record = files_service.finalize_job_output(
                        job_id=job_id,
                        job_dir=job_dir,
                        output_filename=output_csv_path.name,
                        status="final",
                        row_count=successful_rows if successful_rows > 0 else processed_rows,
                        base_name=output_csv_path.name,
                    )

                    if file_record:
                        app_root = get_app_data_root()
                        try:
                            relative_output = str(Path(file_record["path"]))
                        except Exception:
                            relative_output = file_record["path"]

                        job_service.mark_completed(
                            job_id,
                            output_file=relative_output,
                            processed_rows=processed_rows if processed_rows > 0 else successful_rows,
                        )
                    else:
                        # Fallback: store the job workspace path if finalization failed
                        app_root = get_app_data_root()
                        try:
                            relative_output = str(output_csv_path.relative_to(app_root))
                        except ValueError:
                            relative_output = str(output_csv_path)

                        job_service.mark_completed(
                            job_id,
                            output_file=relative_output,
                            processed_rows=processed_rows if processed_rows > 0 else successful_rows,
                        )
            else:
                job = job_service.get_job(job_id)  # refresh
                if job and job.get("status") == "cancelling":
                    # Double-check: if status is cancelling but we didn't handle it above
                    actual_successful = _count_successful_rows_from_threads(job_dir)
                    if requested_rows > 0:
                        try:
                            quota_service.settle_quota(job_id, requested_rows, actual_successful)
                        except Exception as exc:
                            logging.error(f"Quota settlement failed for cancelling job {job_id}: {exc}")
                    job_service.mark_cancelled(job_id, actual_successful)
                else:
                    error_snippet = _tail_log(log_path, lines=20)
                    job_service.mark_failed(
                        job_id,
                        error=f"Runner exited with code {return_code}.\n{error_snippet}",
                    )

    except Exception as exc:
        with _process_lock:
            _running_processes.pop(job_id, None)
        # On exception, release reserved quota (but don't consume)
        job = job_service.get_job(job_id)
        requested = job.get("requested_rows", 0) if job else 0
        if requested > 0:
            try:
                quota_service.release_reserved(job_id, requested)
            except Exception as quota_exc:
                logging.error(f"Failed to release reserved quota for job {job_id}: {quota_exc}")
                exc = Exception(f"{exc} (quota release failed: {quota_exc})")
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

    if job.get("status") not in ("running", "created"):
        return False

    job_service.mark_cancelling(job_id)

    jobs_root = get_jobs_dir()
    job_dir = jobs_root / job_id
    cancel_file = job_dir / ".cancel"
    try:
        cancel_file.touch()
    except Exception as e:
        logging.warning(f"Could not create .cancel file for job {job_id}: {e}")

    with _process_lock:
        proc = _running_processes.get(job_id)

    if proc:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        except Exception as e:
            logging.warning(f"Error terminating subprocess for job {job_id}: {e}")

    return True
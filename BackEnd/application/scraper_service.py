""" scraper_service.py — Orchestrates the full lifecycle of a scraping job. """

from __future__ import annotations
import csv
import io
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Dict

import psutil

from application import config
from application import job_service
from application import quota_service
from application import files_service
from application.storage import get_app_data_root, get_jobs_dir

_running_processes: Dict[str, subprocess.Popen] = {}
_process_ready_events: Dict[str, threading.Event] = {}
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
    quick_scrape: bool = False,
) -> None:
    """Prepare the job workspace and launch the scraper in a background thread."""
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
            quick_scrape,
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


def _count_successful_rows_from_threads(job_dir: Path) -> int:
    """Count successfully scraped rows from thread CSV files in the workspace."""
    workspace_dir = job_dir / "workspace"
    if not workspace_dir.exists():
        return 0
    total = 0
    for thread_file in workspace_dir.glob("thread_*.csv"):
        try:
            with open(thread_file, "r", encoding="utf-8") as fh:
                total += max(0, sum(1 for _ in csv.reader(fh)) - 1)
        except Exception:
            continue
    return total


def _is_cancelled(job_dir: Path) -> bool:
    return (job_dir / ".cancel").exists()


def _terminate_process_tree(pid: int) -> None:
    """Terminate the process and all its children (cross‑platform)."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        parent.terminate()
        # Wait up to 5 seconds for graceful termination
        gone, alive = psutil.wait_procs(children + [parent], timeout=5)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass


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
    quick_scrape: bool,
) -> None:
    """
    Run the ScraperEngine subprocess, then settle quota based on successful rows.
    Quota is reconciled using the number of valid successful rows (excluding timeouts and failures).
    This function does NOT handle cancellation finalization; that is owned by _cancel_worker.
    """
    # ---- 1. Check cancellation BEFORE marking running ----
    if _is_cancelled(job_dir):
        logging.info(f"Job {job_id} cancelled before engine start; not marking running.")
        # The cancellation worker will finalize the job.
        return

    # ---- 2. Atomically transition from 'created' to 'running' ----
    updated_job = job_service.mark_running_if_created(job_id)
    if not updated_job:
        # Another thread already changed state (e.g., cancellation won the race)
        logging.info(f"Job {job_id} state changed before we could mark running; aborting.")
        return

    # ---- 3. Create and register process-ready event ----
    ready_event = threading.Event()
    with _process_lock:
        _process_ready_events[job_id] = ready_event

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
                # Signal that the process is registered
                ready_event.set()

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
                                successful_rows = event.get("successful", 0)
                                timeout_count = event.get("timeout", 0)
                                failure_count = event.get("failed", 0)
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

            # ---- 4. Remove process from registry and clear event ----
            with _process_lock:
                _running_processes.pop(job_id, None)
                _process_ready_events.pop(job_id, None)

            # ---- 5. Check if cancellation was requested during the run ----
            job = job_service.get_job(job_id)
            if job and job.get("status") == "cancelling":
                # Cancellation worker will handle finalization; just exit.
                logging.info(f"Job {job_id} was cancelled during engine run; not finalizing.")
                return

            # ---- 6. Normal completion / failure path (only if not cancelled) ----
            requested_rows = job.get("requested_rows", 0) if job else 0

            # If no "completed" event was received, fall back to counting thread files
            if successful_rows == 0:
                successful_rows = _count_successful_rows_from_threads(job_dir)

            # Settle quota (idempotent)
            quota_failed = False
            quota_error = None
            if requested_rows > 0:
                try:
                    quota_service.settle_quota(job_id, requested_rows, successful_rows)
                except Exception as exc:
                    quota_failed = True
                    quota_error = str(exc)
                    logging.error(f"Quota settlement failed for job {job_id}: {exc}")

            # Update job status
            if return_code == 0 and output_csv_path.is_file():
                if quota_failed:
                    job_service.mark_failed(
                        job_id,
                        error=f"Scraping succeeded but quota finalization failed: {quota_error}",
                    )
                else:
                    # Finalize output to Files directory
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
                        processed_rows = _count_csv_rows(output_csv_path)
                        job_service.mark_completed(
                            job_id,
                            output_file=relative_output,
                            processed_rows=processed_rows if processed_rows > 0 else successful_rows,
                        )
                    else:
                        app_root = get_app_data_root()
                        try:
                            relative_output = str(output_csv_path.relative_to(app_root))
                        except ValueError:
                            relative_output = str(output_csv_path)
                        processed_rows = _count_csv_rows(output_csv_path)
                        job_service.mark_completed(
                            job_id,
                            output_file=relative_output,
                            processed_rows=processed_rows if processed_rows > 0 else successful_rows,
                        )
            else:
                error_snippet = _tail_log(log_path, lines=20)
                job_service.mark_failed(
                    job_id,
                    error=f"Runner exited with code {return_code}.\n{error_snippet}",
                )

    except Exception as exc:
        with _process_lock:
            _running_processes.pop(job_id, None)
            _process_ready_events.pop(job_id, None)
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


# ---- Cancellation machinery ----

def cancel_job(job_id: str) -> bool:
    """
    Request cancellation of a running job.
    Creates a .cancel flag file and starts the cancellation worker.
    Returns True if the job was successfully marked as cancelling.
    """
    job = job_service.get_job(job_id)
    if not job:
        return False

    status = job.get("status")
    if status not in ("running", "created"):
        return False

    # Prevent duplicate cancellation threads
    if status == "cancelling":
        return True

    # Atomically transition to cancelling (only if still running/created)
    updated = job_service.mark_cancelling(job_id)
    if not updated:
        # Race: job already completed or failed
        return False

    jobs_root = get_jobs_dir()
    job_dir = jobs_root / job_id
    cancel_file = job_dir / ".cancel"
    try:
        cancel_file.touch()
    except Exception as e:
        logging.warning(f"Could not create .cancel file for job {job_id}: {e}")

    # Start the cancellation worker (background thread)
    threading.Thread(
        target=_cancel_worker,
        args=(job_id,),
        daemon=True,
        name=f"cancel-{job_id[:8]}",
    ).start()

    return True


def _cancel_worker(job_id: str) -> None:
    """
    Two-phase cancellation:
    1. Wait for process registration (or timeout).
    2. If process exists, wait for graceful exit (grace period).
    3. If still alive, force‑kill the process tree.
    4. Finalize cancellation (quota, output, status).
    """
    grace = config.CANCELLATION_GRACE_PERIOD

    # ---- 1. Wait for process registration ----
    ready_event = None
    with _process_lock:
        ready_event = _process_ready_events.get(job_id)
    if ready_event is not None:
        # Wait for the process to be registered, but not longer than the grace period
        registered = ready_event.wait(timeout=grace)
        if not registered:
            logging.warning(f"Job {job_id} process did not register within {grace}s; proceeding without it.")
            # Proceed with finalization (no process to kill)
            _finalize_cancellation(job_id)
            return

    # ---- 2. Get the process ----
    proc = None
    with _process_lock:
        proc = _running_processes.get(job_id)

    if proc is None:
        # Process never started or already finished; finalize directly
        _finalize_cancellation(job_id)
        return

    # ---- 3. Graceful shutdown attempt ----
    start = time.time()
    while time.time() - start < grace:
        poll = proc.poll()
        if poll is not None:
            # Process exited on its own
            break
        time.sleep(1)
    else:
        # Grace period expired → force‑kill the process tree
        logging.info(f"Force‑terminating process tree for job {job_id} (PID {proc.pid})")
        _terminate_process_tree(proc.pid)
        # Wait for the process to be reaped
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    # ---- 4. Clean up process registry (in case _run_engine didn't) ----
    with _process_lock:
        _running_processes.pop(job_id, None)
        _process_ready_events.pop(job_id, None)

    # ---- 5. Finalize cancellation ----
    _finalize_cancellation(job_id)


def _finalize_cancellation(job_id: str) -> None:
    """
    Idempotent finalization of a cancelled job.
    - Settles quota (releases unused rows).
    - Preserves partial output if any rows succeeded.
    - Atomically marks job as 'cancelled' only if still 'cancelling'.
    """
    # ---- 1. Check status ----
    job = job_service.get_job(job_id)
    if not job:
        logging.warning(f"Job {job_id} not found during cancellation finalization.")
        return
    if job.get("status") != "cancelling":
        logging.info(f"Job {job_id} status is {job.get('status')}; skipping finalization.")
        return

    jobs_root = get_jobs_dir()
    job_dir = jobs_root / job_id

    # ---- 2. Count successful rows ----
    successful_rows = _count_successful_rows_from_threads(job_dir)

    # ---- 3. Settle quota (releases unused rows) ----
    requested_rows = job.get("requested_rows", 0)
    if requested_rows > 0:
        try:
            quota_service.settle_quota(job_id, requested_rows, successful_rows)
        except Exception as exc:
            logging.error(f"Quota settlement failed during cancellation for job {job_id}: {exc}")

    # ---- 4. Finalize partial output (if any rows succeeded) ----
    output_filename = job.get("output_filename")  # stored in job record
    if output_filename and successful_rows > 0:
        output_csv_path = job_dir / output_filename
        if output_csv_path.is_file():
            files_service.finalize_job_output(
                job_id=job_id,
                job_dir=job_dir,
                output_filename=output_filename,
                status="partial",
                row_count=successful_rows,
                base_name=output_filename,
            )
            # Optionally update job's output_file path (will be set in mark_cancelled_if_cancelling)
            # We'll rely on mark_cancelled_if_cancelling to set output_file if needed.

    # ---- 5. Atomically mark as cancelled ----
    updated = job_service.mark_cancelled_if_cancelling(job_id, successful_rows)
    if updated:
        logging.info(f"Job {job_id} successfully cancelled with {successful_rows} rows processed.")
    else:
        logging.warning(f"Job {job_id} status changed before we could mark cancelled; may have been completed.")
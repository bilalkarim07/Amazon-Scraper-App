""" progress_reporter.py — Thread-safe progress tracking with JSON emission. """

import json
import threading
from typing import Optional
from utils.logger import logger


class ProgressReporter:
    """Thread-safe progress counter that emits JSON events to stdout."""

    def __init__(self, total: int = 0):
        self._total = total
        self._processed = 0
        self._lock = threading.RLock()
        self._cancelled = False

    def set_total(self, total: int) -> None:
        with self._lock:
            self._total = total

    def increment(self, n: int = 1) -> int:
        """Increment processed count by n. Returns new processed count."""
        logger.info("[progress] increment: acquiring lock")
        with self._lock:
            logger.info("[progress] increment: lock acquired")
            self._processed += n
            processed = self._processed
            total = self._total
        logger.info("[progress] increment: lock released")

        # Emit AFTER releasing the lock to avoid deadlock.
        self._emit_progress(processed, total)

        logger.info("[progress] increment: progress emitted")
        return processed

    def set_processed(self, value: int) -> None:
        """Set processed count to a specific value."""
        logger.info("[progress] set_processed: acquiring lock")
        with self._lock:
            self._processed = value
            processed = self._processed
            total = self._total
        logger.info("[progress] set_processed: lock released")

        # Emit AFTER releasing the lock.
        self._emit_progress(processed, total)

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    @property
    def processed(self) -> int:
        with self._lock:
            return self._processed

    def _emit_progress(self, processed: int, total: int) -> None:
        """Emit progress JSON to stdout. Does NOT acquire the lock."""
        percentage = round((processed / total) * 100, 1) if total else 0.0

        data = {
            "event": "progress",
            "processed": processed,
            "total": total,
            "percentage": percentage,
        }

        logger.info(f"[progress] emitting JSON: {data}")
        print(json.dumps(data), flush=True)
        logger.info("[progress] JSON emitted")

    def emit_started(self) -> None:
        """Emit a started event with the correct total."""
        with self._lock:
            data = {
                "event": "started",
                "processed": 0,
                "total": self._total,
            }
        print(json.dumps(data), flush=True)

    def emit_completed(self) -> None:
        """Emit a completed event."""
        with self._lock:
            data = {
                "event": "completed",
                "processed": self._processed,
                "total": self._total,
            }
        print(json.dumps(data), flush=True)

    def emit_failed(self, error: str) -> None:
        """Emit a failed event."""
        with self._lock:
            data = {
                "event": "failed",
                "error": error,
                "processed": self._processed,
                "total": self._total,
            }
        print(json.dumps(data), flush=True)

    def mark_cancelled(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled
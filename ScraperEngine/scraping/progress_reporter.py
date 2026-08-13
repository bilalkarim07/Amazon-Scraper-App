""" progress_reporter.py — Thread-safe progress tracking with JSON emission. """

import json
import threading
from typing import Optional


class ProgressReporter:
    """Thread-safe progress counter that emits JSON events to stdout."""

    def __init__(self, total: int = 0):
        self._total = total
        self._processed = 0
        self._lock = threading.Lock()
        self._cancelled = False

    def set_total(self, total: int) -> None:
        with self._lock:
            self._total = total

    def increment(self, n: int = 1) -> int:
        """Increment processed count by n. Returns new processed count."""
        with self._lock:
            self._processed += n
            self._emit_progress()
            return self._processed

    def set_processed(self, value: int) -> None:
        with self._lock:
            self._processed = value
            self._emit_progress()

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    @property
    def processed(self) -> int:
        with self._lock:
            return self._processed

    @property
    def progress_percentage(self) -> float:
        with self._lock:
            if self._total == 0:
                return 0.0
            return (self._processed / self._total) * 100

    def _emit_progress(self) -> None:
        data = {
            "event": "progress",
            "processed": self._processed,
            "total": self._total,
            "percentage": round(self.progress_percentage, 1),
        }
        print(json.dumps(data), flush=True)

    def emit_completed(self) -> None:
        data = {
            "event": "completed",
            "processed": self._processed,
            "total": self._total,
        }
        print(json.dumps(data), flush=True)

    def emit_failed(self, error: str) -> None:
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
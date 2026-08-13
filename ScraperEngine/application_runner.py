#!/usr/bin/env python
"""
application_runner.py — CLI entry point for the ScraperEngine.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add src to path so we can import amazon_scraper
sys.path.insert(0, str(Path(__file__).parent / "src"))

from amazon_scraper import AmazonScraper  # type: ignore


def emit(event: str, **kwargs) -> None:
    """Emit a structured JSON event to stdout."""
    data = {"event": event, **kwargs}
    print(json.dumps(data), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Amazon Scraper Engine Runner")
    parser.add_argument("--job-id", required=True, help="Unique job identifier")
    parser.add_argument("--job-dir", required=True, help="Job directory path")
    parser.add_argument("--input-csv", required=True, help="Path to input CSV")
    parser.add_argument("--output-csv", required=True, help="Path to output CSV")
    parser.add_argument("--threads", type=int, default=3, help="Number of threads")
    parser.add_argument("--first-page-wait", type=int, default=150, help="First page wait in seconds")
    parser.add_argument("--next-page-wait", type=int, default=5, help="Next page wait in seconds")
    parser.add_argument("--keywords", type=str, default="", help="Comma-separated keywords")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    args = parser.parse_args()

    print(f"[runner] Job ID: {args.job_id}", flush=True)
    print(f"[runner] Headless: {args.headless}", flush=True)
    print(f"[runner] Input: {args.input_csv}", flush=True)
    print(f"[runner] Output: {args.output_csv}", flush=True)
    print(f"[runner] Threads: {args.threads}", flush=True)

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else []

    # Cancellation flag file
    cancel_file = Path(args.job_dir) / ".cancel"
    cancel_file.parent.mkdir(parents=True, exist_ok=True)

    def is_cancelled() -> bool:
        return cancel_file.exists()

    try:
        # Use Selenium Manager — no hardcoded chromedriver.exe
        scraper = AmazonScraper(
            listings=args.input_csv,
            max_threads=args.threads,
            webdriver_file=None,          # Use Selenium Manager
            workspace_dir=args.job_dir,
        )

        # Run extraction + processing
        scraper.extract_process(
            output=args.output_csv,
            price_symbol="$",
            base_append="https://www.amazon.com/",
            keywords=keywords,
            first_page_wait=args.first_page_wait,
            next_page_wait=args.next_page_wait,
            headless=args.headless,
            cancel_check=is_cancelled,
        )

        if is_cancelled():
            emit("cancelled", processed=0, total=0)
            sys.exit(0)

        # Count output rows
        try:
            import csv
            with open(args.output_csv, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = sum(1 for _ in reader) - 1
                emit("completed", processed=rows, total=rows)
        except Exception:
            emit("completed", processed=0, total=0)

        sys.exit(0)

    except Exception as exc:
        emit("failed", error=str(exc))
        print(f"[runner] Error: {exc}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
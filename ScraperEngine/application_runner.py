#!/usr/bin/env python3
"""
Application runner for the Amazon Scraper.
Called by the backend to start a scraping job.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# Add parent directory to path so we can import from the engine
sys.path.insert(0, str(Path(__file__).parent.parent))

from amazon_scraper import AmazonScraper


def parse_keywords(keywords_str: str) -> list[str]:
    """Parse comma-separated keywords into a list."""
    if not keywords_str:
        return []
    return [k.strip() for k in keywords_str.split(",") if k.strip()]


def main():
    parser = argparse.ArgumentParser(description="Run Amazon scraper job")
    parser.add_argument("--job-id", required=True, help="Job ID")
    parser.add_argument("--job-dir", required=True, help="Job directory")
    parser.add_argument("--input-csv", required=True, help="Input CSV file path")
    parser.add_argument("--output-csv", required=True, help="Output CSV file path")
    parser.add_argument("--threads", type=int, default=3, help="Number of threads")
    parser.add_argument("--first-page-wait", type=int, default=10, help="First page wait in seconds")
    parser.add_argument("--next-page-wait", type=int, default=3, help="Next page wait in seconds")
    parser.add_argument("--keywords", default="", help="Comma-separated keywords")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    # Marketplace arguments
    parser.add_argument("--marketplace", required=True, help="Marketplace identifier (e.g., US, UK)")
    parser.add_argument("--base-url", required=True, help="Base URL for the marketplace")
    parser.add_argument("--currency-code", required=True, help="Currency code (e.g., USD)")
    parser.add_argument("--currency-symbol", required=True, help="Currency symbol (e.g., $)")

    args = parser.parse_args()

    # Ensure job directory exists
    job_dir = Path(args.job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    # Read URLs from input CSV (first column)
    urls = []
    with open(args.input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            url_col = reader.fieldnames[0]
            for row in reader:
                url = row.get(url_col, "").strip()
                if url:
                    urls.append(url)

    if not urls:
        print(json.dumps({"event": "failed", "error": "No URLs found in input CSV"}))
        sys.exit(1)

    keywords = parse_keywords(args.keywords)

    # --- CANCELLATION CHECK: check for .cancel flag file ---
    cancel_file = job_dir / ".cancel"

    def cancel_check() -> bool:
        """Return True if cancellation has been requested via the .cancel flag file."""
        return cancel_file.exists()

    # Instantiate scraper with all parameters
    scraper = AmazonScraper(
        listings=urls,
        max_threads=args.threads,
        workspace_dir=args.job_dir,
        marketplace=args.marketplace,
        base_url=args.base_url,
        currency_code=args.currency_code,
        currency_symbol=args.currency_symbol,
    )

    # Run the extraction and processing pipeline
    try:
        scraper.extract_process(
            output=args.output_csv,
            keywords=keywords,
            first_page_wait=args.first_page_wait,
            next_page_wait=args.next_page_wait,
            headless=args.headless,
            cancel_check=cancel_check,  # Pass cancellation callback
        )
    except Exception as e:
        print(json.dumps({"event": "failed", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
application_runner.py — CLI bridge between the FastAPI BackEnd and the AmazonScraper engine.

Invoked by the BackEnd's scraper_service.py as a subprocess:

    uv run python application_runner.py \\
        --job-id <job_id> \\
        --job-dir <absolute/path/to/job/dir> \\
        --input-csv <absolute/path/to/input.csv> \\
        --output-csv <absolute/path/to/output.csv> \\
        --threads <int> \\
        --first-page-wait <int_seconds> \\
        --next-page-wait <int_seconds> \\
        [--keywords kw1,kw2,kw3] \\
        [--headless]

Exit codes:
    0 — success, output CSV written to --output-csv
    1 — validation / engine error
"""

import sys
import os
import argparse
import traceback


def main():
    parser = argparse.ArgumentParser(description="Amazon Scraper — Application Runner")

    parser.add_argument("--job-id",          required=True,  help="Unique job identifier")
    parser.add_argument("--job-dir",         required=True,  help="Absolute path to job workspace directory")
    parser.add_argument("--input-csv",       required=True,  help="Absolute path to normalised input CSV")
    parser.add_argument("--output-csv",      required=True,  help="Absolute path where final output CSV is written")
    parser.add_argument("--threads",         required=True,  type=int, help="Number of parallel threads (1–5)")
    parser.add_argument("--first-page-wait", required=True,  type=int, help="Wait time for first page (seconds)")
    parser.add_argument("--next-page-wait",  required=True,  type=int, help="Wait time for subsequent pages (seconds)")
    parser.add_argument("--keywords",        default="",     help="Comma-separated keyword list (optional)")
    parser.add_argument("--headless",        action="store_true", help="Run Chrome in headless mode")

    args = parser.parse_args()

    print(f"[runner] Job ID     : {args.job_id}", flush=True)
    print(f"[runner] Job dir    : {args.job_dir}", flush=True)
    print(f"[runner] Input CSV  : {args.input_csv}", flush=True)
    print(f"[runner] Output CSV : {args.output_csv}", flush=True)
    print(f"[runner] Threads    : {args.threads}", flush=True)
    print(f"[runner] First wait : {args.first_page_wait}s", flush=True)
    print(f"[runner] Next wait  : {args.next_page_wait}s", flush=True)
    print(f"[runner] Keywords   : {args.keywords!r}", flush=True)
    print(f"[runner] Headless   : {args.headless}", flush=True)

    # Parse keywords
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else []

    # Validate inputs before importing heavy deps
    if not os.path.isfile(args.input_csv):
        print(f"[runner] ERROR: Input CSV not found: {args.input_csv}", flush=True)
        sys.exit(1)

    if not os.path.isdir(args.job_dir):
        print(f"[runner] ERROR: Job directory not found: {args.job_dir}", flush=True)
        sys.exit(1)

    try:
        from amazon_scraper import AmazonScraper

        scraper = AmazonScraper(
            listings=args.input_csv,
            max_threads=args.threads,
            workspace_dir=args.job_dir,
        )

        result_path = scraper.extract_process(
            output=args.output_csv,
            keywords=keywords,
            first_page_wait=args.first_page_wait,
            next_page_wait=args.next_page_wait,
            headless=args.headless,
        )

        if not os.path.isfile(result_path):
            print(f"[runner] ERROR: Scraper finished but output file missing: {result_path}", flush=True)
            sys.exit(1)

        print(f"[runner] SUCCESS: Output written to {result_path}", flush=True)
        sys.exit(0)

    except Exception as e:
        print(f"[runner] FATAL ERROR: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

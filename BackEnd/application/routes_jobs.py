"""routes_jobs.py — Job management endpoints."""

from __future__ import annotations
from typing import Annotated
import csv
import io
from fastapi import APIRouter, Form, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from application import quota_service
from application import job_service
from application import scraper_service
from application import marketplace_config
from application import files_service
from application.models import JobCreateResponse, JobStatusResponse, CancelResponse
from application.config import DEFAULT_FIRST_PAGE_WAIT, DEFAULT_NEXT_PAGE_WAIT, HEADLESS_MODE
from application.files_service import sanitize_filename

router = APIRouter()


@router.post(
    "/api/jobs",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Jobs"],
    summary="Upload a CSV and start a scraping job",
)
async def create_job(
    file: Annotated[UploadFile, File(description="CSV containing product URLs")],
    column: Annotated[str, Form(description="Column header that holds the product URLs")] = "Links",
    threads: Annotated[int, Form(ge=1, le=5, description="Parallel browser threads")] = 3,
    first_page_wait: Annotated[int, Form(ge=1, description="Seconds to wait for the first page")] = DEFAULT_FIRST_PAGE_WAIT,
    next_page_wait: Annotated[int, Form(ge=1, description="Seconds to wait for subsequent pages")] = DEFAULT_NEXT_PAGE_WAIT,
    output_filename: Annotated[str, Form(description="Output CSV filename")] = "output.csv",
    keywords: Annotated[str, Form(description="Comma-separated keywords")] = "",
    headless: Annotated[bool, Form(description="Run Chrome headless")] = HEADLESS_MODE,
    marketplace: Annotated[str, Form(description="Marketplace identifier")] = "US",
    currency_code: Annotated[str, Form(description="Currency code")] = "USD",
    currency_symbol: Annotated[str, Form(description="Currency symbol")] = "$",
    quick_scrape: Annotated[bool, Form(description="Run a credit-free Quick Scrape job")] = False,
) -> JobCreateResponse:
    """Create a scraper job.

    Normal jobs reserve quota before starting. Quick Scrape jobs are intentionally
    quota-free and are limited to 10 input rows. The existing scraper pipeline is
    reused; Quick Scrape simply arrives with a one-thread configuration and no
    quota reservation.
    """
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only .csv files are accepted.",
        )

    csv_bytes = await file.read()
    if not csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )

    try:
        text = csv_bytes.decode("utf-8-sig", errors="ignore")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        headers_reader = csv.reader(io.StringIO(first_line))
        headers = next(headers_reader, [])
        headers = [h.strip() for h in headers if h.strip()]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_CSV", "message": f"Failed to parse CSV headers: {str(exc)}"},
        )

    matched_column = next((h for h in headers if h.lower() == column.lower()), None)
    if not matched_column:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_COLUMN",
                "message": f"Column '{column}' does not exist in the uploaded CSV.",
                "requested_column": column,
                "available_columns": headers,
            },
        )
    column = matched_column

    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        total_rows = len(rows)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_CSV", "message": f"Failed to parse CSV: {str(exc)}"},
        )

    if total_rows <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded CSV contains no data rows.",
        )

    if quick_scrape:
        if total_rows > 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "QUICK_SCRAPE_LIMIT",
                    "message": "Quick Scrape accepts at most 10 Amazon product links.",
                    "limit": 10,
                    "requested": total_rows,
                },
            )
        # Backend is authoritative: Quick Scrape always uses one worker.
        threads = 1

    if not marketplace_config.validate_marketplace(marketplace):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid marketplace: {marketplace}",
        )

    marketplace_config_obj = marketplace_config.get_marketplace(marketplace)
    if marketplace == "ALL_EUROPE":
        currency_code = "AUTO"
        currency_symbol = "AUTO"

    # Quick Scrape deliberately does NOT reserve quota.
    if not quick_scrape:
        success, error_msg = quota_service.reserve_quota(total_rows)
        if not success:
            quota = quota_service.get_quota()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "QUOTA_EXCEEDED",
                    "message": error_msg,
                    "daily_limit": quota["daily_limit"],
                    "used": quota["used"],
                    "reserved": quota["reserved"],
                    "remaining": quota["remaining"],
                    "requested": total_rows,
                },
            )

    output_filename = sanitize_filename(output_filename)
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []

    # requested_rows is the authoritative quota reservation amount. Keeping it at
    # zero for Quick Scrape means the existing settlement path performs no quota
    # mutation after the job completes or is cancelled.
    requested_rows = 0 if quick_scrape else total_rows

    job = job_service.create_job(
        total_rows=total_rows,
        marketplace=marketplace,
        domain=marketplace_config_obj.get("domain") if marketplace_config_obj else None,
        currency_code=currency_code,
        currency_symbol=currency_symbol,
        requested_rows=requested_rows,
    )
    job_id = job["id"]

    try:
        scraper_service.start_job(
            job_id=job_id,
            csv_bytes=csv_bytes,
            column_name=column,
            threads=threads,
            first_page_wait=first_page_wait,
            next_page_wait=next_page_wait,
            output_filename=output_filename,
            keywords=keyword_list,
            headless=headless,
            marketplace=marketplace,
            currency_code=currency_code,
            currency_symbol=currency_symbol,
        )
    except Exception:
        if not quick_scrape:
            quota_service.release_reserved(job_id, total_rows)
        raise

    return JobCreateResponse(job_id=job_id, status="created")


@router.get(
    "/api/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    summary="Get the current status of a scraping job",
)
async def get_job(job_id: str) -> JobStatusResponse:
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")
    return JobStatusResponse(**job)


@router.post(
    "/api/jobs/{job_id}/cancel",
    response_model=CancelResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Jobs"],
    summary="Cancel a running scraping job",
)
async def cancel_job(job_id: str) -> CancelResponse:
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")
    if job.get("status") not in ("running", "created"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel job with status '{job.get('status')}'. Only running or created jobs can be cancelled.",
        )
    if not scraper_service.cancel_job(job_id):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cancel job.")
    return CancelResponse(job_id=job_id, status="cancelling")


@router.get(
    "/api/jobs/{job_id}/download",
    tags=["Jobs"],
    summary="Download the output CSV file generated by a job",
)
async def download_job_output(job_id: str):
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found.")

    file_records = files_service.list_files_by_job(job_id)
    if not file_records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No output file found for job '{job_id}'.")

    file_record = file_records[0]
    if file_record.get("deleted_at") is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="The output file for this job has been deleted.")

    file_path = files_service.resolve_file_path(file_record)
    if file_path is None or not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The physical output file is missing from disk.")

    return FileResponse(path=str(file_path), media_type="text/csv", filename=file_record["filename"])

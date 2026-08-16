""" routes_jobs.py — Job management endpoints. """

from __future__ import annotations
from typing import Annotated, Optional
import csv
import io
from fastapi import APIRouter, Form, HTTPException, UploadFile, File, status
from application import quota_service
from application import job_service
from application import scraper_service
from application import marketplace_config
from application.models import JobCreateResponse, JobStatusResponse, CancelResponse
from application.config import DEFAULT_FIRST_PAGE_WAIT, DEFAULT_NEXT_PAGE_WAIT, HEADLESS_MODE
from application.files_service import sanitize_filename  # <-- Added import

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/jobs — create and start a job
# ---------------------------------------------------------------------------

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
) -> JobCreateResponse:
    # --- Validate file type ---
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

    # --- Validate CSV Column ---
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

    matched_column = None
    for h in headers:
        if h.lower() == column.lower():
            matched_column = h
            break

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

    # --- Get total rows from CSV ---
    try:
        lines = [line for line in text.splitlines() if line.strip()]
        total_rows = max(0, len(lines) - 1)  # Subtract header row
    except Exception:
        total_rows = 0

    # --- Validate marketplace ---
    if not marketplace_config.validate_marketplace(marketplace):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid marketplace: {marketplace}",
        )

    marketplace_config_obj = marketplace_config.get_marketplace(marketplace)

    # For ALL_EUROPE, currency is auto-detected
    if marketplace == "ALL_EUROPE":
        currency_code = "AUTO"
        currency_symbol = "AUTO"

    # --- RESERVE QUOTA (atomic) ---
    if total_rows > 0:
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
    else:
        # No rows – reserve 0 (should not happen, but safe)
        quota_service.reserve_quota(0)

    # --- Validate / sanitise output filename ---
    output_filename = sanitize_filename(output_filename)  # <-- Changed to use sanitize_filename

    # --- Parse keywords ---
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []

    # --- Create the job record ---
    job = job_service.create_job(
        total_rows=total_rows,
        marketplace=marketplace,
        domain=marketplace_config_obj.get("domain") if marketplace_config_obj else None,
        currency_code=currency_code,
        currency_symbol=currency_symbol,
        requested_rows=total_rows,
    )
    job_id = job["id"]

    # --- Kick off the scraper in the background ---
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

    return JobCreateResponse(job_id=job_id, status="created")


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id} — query job status
# ---------------------------------------------------------------------------

@router.get(
    "/api/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    summary="Get the current status of a scraping job",
)
async def get_job(job_id: str) -> JobStatusResponse:
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )
    return JobStatusResponse(**job)


# ---------------------------------------------------------------------------
# POST /api/jobs/{job_id}/cancel — cancel a running job
# ---------------------------------------------------------------------------

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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    if job.get("status") not in ("running", "created"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel job with status '{job.get('status')}'. Only running or created jobs can be cancelled.",
        )

    success = scraper_service.cancel_job(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel job.",
        )

    return CancelResponse(job_id=job_id, status="cancelling")
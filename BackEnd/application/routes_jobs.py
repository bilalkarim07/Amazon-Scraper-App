""" routes_jobs.py — Job management endpoints. """

from __future__ import annotations
from typing import Annotated, Optional
import csv
import io
from fastapi import APIRouter, Form, HTTPException, UploadFile, File, status
from application import job_service, scraper_service
from application.models import JobCreateResponse, JobStatusResponse, CancelResponse
from application.config import DEFAULT_FIRST_PAGE_WAIT, DEFAULT_NEXT_PAGE_WAIT, HEADLESS_MODE

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
    headless: Annotated[bool, Form(description="Run Chrome headless")] = HEADLESS_MODE,  # Now uses env var
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

    # --- Validate / sanitise output filename ---
    output_filename = output_filename.strip()
    if not output_filename:
        output_filename = "output.csv"
    if not output_filename.lower().endswith(".csv"):
        output_filename += ".csv"

    # --- Parse keywords ---
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []

    # --- Create the job record ---
    job = job_service.create_job(total_rows=0)
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
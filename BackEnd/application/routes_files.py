"""
routes_files.py — File download endpoint.

GET /api/jobs/{job_id}/download
    Streams the completed job's output CSV back to the client.
    Returns 404 if the job doesn't exist or hasn't completed yet.
    Returns 404 if the output file is missing from disk.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from application import file_service

router = APIRouter()


@router.get(
    "/api/jobs/{job_id}/download",
    tags=["Files"],
    summary="Download the output CSV for a completed job",
)
async def download_job_output(job_id: str) -> FileResponse:
    path = file_service.get_output_path(job_id)

    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Output file for job '{job_id}' is not available yet or does not exist.",
        )

    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename=path.name,
    )

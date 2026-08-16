# BackEnd/application/routes_files.py

""" routes_files.py — Persistent file management endpoints. """

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status, Body
from fastapi.responses import FileResponse
from typing import Optional, List

from application import files_service
from application.files_service import get_file, list_files, resolve_file_path, update_file, delete_file

router = APIRouter()


@router.get(
    "/api/files",
    tags=["Files"],
    summary="List all persistent files",
)
async def list_all_files(include_deleted: bool = Query(False, description="Include soft-deleted files")):
    """
    Return metadata for all persistent files.
    Excludes soft-deleted files by default.
    """
    files = files_service.list_files(include_deleted=include_deleted)
    # Remove physical path information from response
    for f in files:
        f.pop("path", None)
    return files


@router.get(
    "/api/files/{file_id}",
    tags=["Files"],
    summary="Get metadata for a specific file",
)
async def get_file_metadata(file_id: int):
    """Return metadata for one persistent file."""
    file_record = get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID {file_id} not found",
        )
    # Remove physical path from response
    file_record.pop("path", None)
    return file_record


@router.get(
    "/api/files/{file_id}/download",
    tags=["Files"],
    summary="Download a persistent file",
)
async def download_file(file_id: int):
    """
    Download the physical CSV file.

    Resolves the stored relative path against the centralized app-data root.
    """
    file_record = get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID {file_id} not found",
        )

    # Check if file is soft-deleted
    if file_record.get("deleted_at") is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This file has been deleted",
        )

    file_path = resolve_file_path(file_record)
    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The physical file is missing from disk",
        )

    return FileResponse(
        path=str(file_path),
        media_type="text/csv",
        filename=file_record["filename"],
    )


@router.patch(
    "/api/files/{file_id}",
    tags=["Files"],
    summary="Update file metadata (e.g., rename, add note)",
)
async def update_file_metadata(
    file_id: int,
    filename: Optional[str] = Body(None),
    marketplace: Optional[str] = Body(None),
    currency_code: Optional[str] = Body(None),
    source_filename: Optional[str] = Body(None),
    note: Optional[str] = Body(None),
):
    """
    Update file metadata.

    Supported updates: filename, marketplace, currency_code, source_filename, note.
    When renaming, the physical file is also renamed.
    """
    # Build update fields
    fields = {}
    if filename is not None:
        fields["filename"] = filename
    if marketplace is not None:
        fields["marketplace"] = marketplace
    if currency_code is not None:
        fields["currency_code"] = currency_code
    if source_filename is not None:
        fields["source_filename"] = source_filename
    if note is not None:
        fields["note"] = note

    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    # Check if file exists and is not deleted
    file_record = get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID {file_id} not found",
        )
    if file_record.get("deleted_at") is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This file has been deleted and cannot be updated",
        )

    updated = update_file(file_id, **fields)
    if updated:
        updated.pop("path", None)
        return updated

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to update file",
    )


@router.delete(
    "/api/files/{file_id}",
    tags=["Files"],
    summary="Soft-delete a file",
)
async def delete_file_endpoint(
    file_id: int,
    remove_physical: bool = Query(True, description="Also delete the physical CSV file"),
):
    """
    Soft-delete a file.

    The file record is marked as deleted and the physical CSV is removed.
    The job workspace is not affected.
    """
    file_record = get_file(file_id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID {file_id} not found",
        )

    if file_record.get("deleted_at") is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This file has already been deleted",
        )

    success = delete_file(file_id, remove_physical=remove_physical)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        )

    return {"message": f"File {file_id} deleted successfully", "file_id": file_id}
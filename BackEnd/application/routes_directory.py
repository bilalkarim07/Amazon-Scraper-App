"""API routes for the persistent Application Directory."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from application import directory_service

router = APIRouter(prefix="/api/directory", tags=["Directory"])


class CreateFolderRequest(BaseModel):
    parent_id: str = "root"
    name: str = Field(min_length=1, max_length=255)


class CreateSheetRequest(BaseModel):
    parent_id: str = "root"
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=2048)


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


@router.get("/root")
async def get_root():
    return {"id": directory_service.ROOT_ID, "name": "Files", "type": "folder", "children": directory_service.list_children()}


@router.get("/{parent_id}/children")
async def get_children(parent_id: str):
    if not directory_service.get_node(parent_id):
        raise HTTPException(404, "Directory not found")
    return {"parent_id": parent_id, "children": directory_service.list_children(parent_id)}


@router.post("/folders", status_code=201)
async def create_folder(request: CreateFolderRequest):
    try:
        return directory_service.create_folder(request.parent_id, request.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(409, "Could not create folder") from exc


@router.post("/google-sheets", status_code=201)
async def create_google_sheet(request: CreateSheetRequest):
    try:
        return directory_service.create_google_sheet(request.parent_id, request.name, request.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(409, "Could not add Google Sheet") from exc


@router.post("/upload", status_code=201)
async def upload_files(parent_id: str = "root", files: list[UploadFile] = File(...)):
    if not directory_service.get_node(parent_id):
        raise HTTPException(404, "Directory not found")
    created = []
    for upload in files:
        if not upload.filename:
            continue
        suffix = Path(upload.filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp_path = Path(temp.name)
            while chunk := await upload.read(1024 * 1024):
                temp.write(chunk)
        try:
            created.append(directory_service.register_file(parent_id, upload.filename, temp_path))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            temp_path.unlink(missing_ok=True)
    return {"files": created}


@router.patch("/{node_id}")
async def rename_node(node_id: str, request: RenameRequest):
    try:
        return directory_service.rename_node(node_id, request.name)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(409, "Could not rename directory item") from exc


@router.delete("/{node_id}")
async def delete_node(node_id: str):
    try:
        directory_service.delete_node(node_id)
        return {"message": "Directory item deleted", "id": node_id}
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

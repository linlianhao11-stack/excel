from __future__ import annotations

from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..services.excel import WORK_DIR, save_upload

router = APIRouter(prefix="/api/files", tags=["files"])

# 内存存储已上传文件信息（MVP 够用，后期换 SQLite）
uploaded_files: dict[str, dict] = {}


@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    results = []
    for f in files:
        if not f.filename or not f.filename.endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(400, f"不支持的文件格式: {f.filename}")
        content = await f.read()
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(400, f"文件过大(>100MB): {f.filename}")
        info = save_upload(f.filename, content)
        uploaded_files[info["file_id"]] = info
        results.append(info)
    return {"files": results}


@router.get("/list")
async def list_files():
    return {"files": list(uploaded_files.values())}


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    info = uploaded_files.pop(file_id, None)
    if not info:
        raise HTTPException(404, "文件不存在")
    path = WORK_DIR / f"{file_id}_{info['filename']}"
    if path.exists():
        path.unlink()
    return {"ok": True}

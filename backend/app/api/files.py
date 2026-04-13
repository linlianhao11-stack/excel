from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..services.excel import WORK_DIR, save_upload
from .auth import get_current_user

router = APIRouter(prefix="/api/files", tags=["files"])

# 内存存储已上传文件信息
uploaded_files: dict[str, dict] = {}


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
):
    results = []
    for f in files:
        if not f.filename or not f.filename.endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(400, f"不支持的文件格式: {f.filename}")
        # 分块读取，防止大文件 OOM
        chunks = []
        total = 0
        max_size = 100 * 1024 * 1024
        while True:
            chunk = await f.read(1024 * 1024)  # 1MB per chunk
            if not chunk:
                break
            total += len(chunk)
            if total > max_size:
                raise HTTPException(400, f"文件过大(>100MB): {f.filename}")
            chunks.append(chunk)
        content = b"".join(chunks)

        try:
            info = save_upload(f.filename, content)
        except Exception as e:
            raise HTTPException(400, f"文件解析失败: {f.filename} - {str(e)}")

        uploaded_files[info["file_id"]] = info
        results.append(info)
    return {"files": results}


@router.get("/list")
async def list_files(user: dict = Depends(get_current_user)):
    return {"files": list(uploaded_files.values())}


@router.delete("/{file_id}")
async def delete_file(file_id: str, user: dict = Depends(get_current_user)):
    info = uploaded_files.pop(file_id, None)
    if not info:
        raise HTTPException(404, "文件不存在")
    path = WORK_DIR / f"{file_id}_{info['filename']}"
    if path.exists():
        path.unlink()
    return {"ok": True}

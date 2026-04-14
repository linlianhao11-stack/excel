from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..services.excel import IMAGE_EXTS, WORK_DIR, preview_excel, save_upload
from .auth import get_current_user

logger = logging.getLogger("excel-agent.files")

router = APIRouter(prefix="/api/files", tags=["files"])

# 内存存储已上传文件信息
uploaded_files: dict[str, dict] = {}

ALLOWED_EXTS = (".xlsx", ".xls", ".csv") + IMAGE_EXTS


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
):
    results = []
    for f in files:
        if not f.filename:
            raise HTTPException(400, "文件名不能为空")
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if f".{ext}" not in ALLOWED_EXTS:
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
        logger.info("文件上传 id=%s name=%s type=%s size=%d", info["file_id"], info["filename"], info.get("type", "excel"), total)
    return {"files": results}


@router.get("/list")
async def list_files(user: dict = Depends(get_current_user)):
    return {"files": list(uploaded_files.values())}


@router.get("/preview-output")
async def preview_output_file(filename: str, user: dict = Depends(get_current_user)):
    """预览 AI 生成的结果文件（前 200 行）"""
    import re
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "非法文件名")
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
        raise HTTPException(400, "非法文件名")
    file_path = WORK_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{ext}" in IMAGE_EXTS:
        raise HTTPException(400, "图片文件不支持表格预览")
    try:
        data = preview_excel(str(file_path), max_rows=200)
    except Exception as e:
        raise HTTPException(500, f"预览失败: {str(e)}")
    return {"sheets": data}


@router.get("/{file_id}/preview")
async def get_file_preview(file_id: str, user: dict = Depends(get_current_user)):
    """返回 Excel 预览数据（前 50 行）"""
    info = uploaded_files.get(file_id)
    if not info:
        raise HTTPException(404, "文件不存在")
    if info.get("type") == "image":
        raise HTTPException(400, "图片文件不支持表格预览")
    try:
        data = preview_excel(info["path"], max_rows=50)
    except Exception as e:
        raise HTTPException(500, f"预览失败: {str(e)}")
    return {"sheets": data}


@router.get("/{file_id}/image")
async def get_file_image(file_id: str, token: str = ""):
    """返回已上传的图片文件（通过 query token 认证，供 <img> 标签使用）"""
    import jwt
    from .auth import JWT_SECRET
    if not token:
        raise HTTPException(401, "未登录")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "无效凭证")

    info = uploaded_files.get(file_id)
    if not info:
        raise HTTPException(404, "文件不存在")
    if info.get("type") != "image":
        raise HTTPException(400, "非图片文件")
    file_path = Path(info["path"])
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    media_type = mimetypes.guess_type(info["filename"])[0] or "image/png"
    return FileResponse(file_path, media_type=media_type)


@router.delete("/{file_id}")
async def delete_file(file_id: str, user: dict = Depends(get_current_user)):
    info = uploaded_files.pop(file_id, None)
    if not info:
        raise HTTPException(404, "文件不存在")
    path = WORK_DIR / f"{file_id}_{info['filename']}"
    if path.exists():
        path.unlink()
    return {"ok": True}

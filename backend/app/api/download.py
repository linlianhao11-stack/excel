from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..services.excel import WORK_DIR
from .auth import get_current_user

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/download")
async def download_file(filename: str, user: dict = Depends(get_current_user)):
    # 只接受文件名，不接受路径，防止路径穿越
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "非法文件名")
    # 只允许安全字符
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
        raise HTTPException(400, "非法文件名")

    file_path = WORK_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

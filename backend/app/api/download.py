from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..services.excel import WORK_DIR

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/download")
async def download_file(path: str):
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    # 安全检查：只允许下载 work 目录下的文件
    try:
        file_path.resolve().relative_to(WORK_DIR.resolve())
    except ValueError:
        raise HTTPException(403, "无权访问该路径")
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

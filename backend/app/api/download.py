from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..database import get_db
from ..services.excel import WORK_DIR
from .auth import get_current_user, JWT_SECRET

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/download")
async def download_file(filename: str, token: str = ""):
    # 支持 query 参数传 token（浏览器直接下载场景）
    if not token:
        raise HTTPException(401, "未登录")
    import jwt as pyjwt
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "无效的登录凭证")
    # 与其他鉴权端点一致：实时校验账号未被禁用
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT is_active FROM users WHERE id = ?", (payload.get("user_id"),)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(401, "账号不存在")
    if not row["is_active"]:
        raise HTTPException(401, "账号已被禁用")
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

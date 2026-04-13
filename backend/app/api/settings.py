from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..database import get_setting, set_setting
from .auth import require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


from typing import Optional


class UpdateSettingsRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


@router.get("")
async def get_settings(admin: dict = Depends(require_admin)):
    api_key = get_setting("api_key", "")
    # 脱敏：只显示后 4 位
    masked_key = f"****{api_key[-4:]}" if len(api_key) > 4 else "未设置"
    return {
        "api_key_masked": masked_key,
        "api_key_set": bool(api_key),
        "base_url": get_setting("base_url", "https://api.deepseek.com"),
        "model": get_setting("model", "deepseek-chat"),
    }


@router.put("")
async def update_settings(
    req: UpdateSettingsRequest, admin: dict = Depends(require_admin)
):
    if req.api_key is not None:
        set_setting("api_key", req.api_key)
    if req.base_url is not None:
        set_setting("base_url", req.base_url)
    if req.model is not None:
        set_setting("model", req.model)
    return {"ok": True}

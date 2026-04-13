from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..database import get_setting, set_setting
from .auth import require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


from typing import Optional


class UpdateSettingsRequest(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


@router.get("")
async def get_settings(admin: dict = Depends(require_admin)):
    from ..services.llm import PROVIDER_DEFAULTS

    provider = get_setting("provider", "deepseek")
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])

    api_key = get_setting("api_key", "")
    masked_key = f"****{api_key[-4:]}" if len(api_key) > 4 else "未设置"
    return {
        "provider": provider,
        "api_key_masked": masked_key,
        "api_key_set": bool(api_key),
        "base_url": get_setting("base_url", defaults["base_url"]),
        "model": get_setting("model", defaults["default_model"]),
        "providers": {
            name: {"models": cfg["models"], "default_base_url": cfg["base_url"]}
            for name, cfg in PROVIDER_DEFAULTS.items()
        },
    }


@router.put("")
async def update_settings(
    req: UpdateSettingsRequest, admin: dict = Depends(require_admin)
):
    if req.provider is not None:
        set_setting("provider", req.provider)
        # 切换服务商时清空旧的 api_key / base_url / model，让新服务商用默认值
        if req.api_key is None:
            set_setting("api_key", "")
        if req.base_url is None:
            from ..services.llm import PROVIDER_DEFAULTS
            defaults = PROVIDER_DEFAULTS.get(req.provider, {})
            set_setting("base_url", defaults.get("base_url", ""))
        if req.model is None:
            from ..services.llm import PROVIDER_DEFAULTS
            defaults = PROVIDER_DEFAULTS.get(req.provider, {})
            set_setting("model", defaults.get("default_model", ""))
    if req.api_key is not None:
        set_setting("api_key", req.api_key)
    if req.base_url is not None:
        set_setting("base_url", req.base_url)
    if req.model is not None:
        set_setting("model", req.model)
    return {"ok": True}

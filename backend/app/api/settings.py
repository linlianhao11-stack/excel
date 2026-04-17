from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..database import get_setting, set_setting
from .auth import get_current_user, require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


from typing import Optional


class UpdateSettingsRequest(BaseModel):
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


@router.get("")
async def get_settings(user: dict = Depends(get_current_user)):
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
    req: UpdateSettingsRequest, user: dict = Depends(get_current_user)
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



class TestConnectionRequest(BaseModel):
    provider: str
    api_key: str
    model: str
    base_url: str = ""


@router.post("/test")
async def test_connection(req: TestConnectionRequest, user: dict = Depends(get_current_user)):
    """测试 LLM 连接是否可用"""
    from ..services.llm import PROVIDER_DEFAULTS, OpenAICompatibleProvider

    defaults = PROVIDER_DEFAULTS.get(req.provider)
    if not defaults:
        return {"ok": False, "message": f"未知服务商: {req.provider}"}

    if not req.api_key:
        # 如果没传 api_key，用已保存的
        api_key = get_setting("api_key", "")
        if not api_key:
            return {"ok": False, "message": "请先填入 API Key"}
    else:
        api_key = req.api_key

    base_url = req.base_url or defaults["base_url"]
    llm = OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=req.model)

    try:
        messages = [{"role": "user", "content": "你好，请回复OK"}]
        response_text = ""
        async for delta in llm.chat_stream(messages, tools=None):
            if delta.get("content"):
                response_text += delta["content"]
                if len(response_text) > 20:
                    break
        if response_text:
            return {"ok": True, "message": f"连接成功，模型已响应"}
        else:
            return {"ok": False, "message": "模型未返回内容"}
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            return {"ok": False, "message": "API Key 无效或已过期"}
        if "404" in error_msg:
            return {"ok": False, "message": f"模型 {req.model} 不存在"}
        if "timeout" in error_msg.lower():
            return {"ok": False, "message": "连接超时，请检查网络"}
        return {"ok": False, "message": f"连接失败: {error_msg[:100]}"}

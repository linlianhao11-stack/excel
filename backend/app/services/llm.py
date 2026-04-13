from __future__ import annotations

import json
import logging
import os
from typing import AsyncGenerator

import httpx

from ..database import get_setting

logger = logging.getLogger("excel-agent.llm")


# 各服务商的默认配置
# base_url 统一遵循 OpenAI SDK 惯例，包含 /v1
PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "env_prefix": "DEEPSEEK",
    },
    "aliyun": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": [
            # Max 系列
            "qwen3-max",
            "qwen-max",
            "qwen-max-latest",
            # Plus 系列
            "qwen3.6-plus",
            "qwen3.5-plus",
            "qwen-plus",
            "qwen-plus-latest",
            # Flash 系列
            "qwen3.5-flash",
            "qwen-flash",
            # Turbo 系列
            "qwen-turbo",
            "qwen-turbo-latest",
            # 推理模型
            "qwq-plus",
            # 视觉模型
            "qwen3-vl-plus",
            "qwen-vl-max",
        ],
        "default_model": "qwen-max-latest",
        "env_prefix": "ALIYUN",
    },
}


class LLMProvider:
    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncGenerator[dict, None]:
        raise NotImplementedError
        yield  # noqa


class OpenAICompatibleProvider(LLMProvider):
    """兼容 OpenAI API 格式的通用 Provider（DeepSeek、阿里云通义千问等）"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncGenerator[dict, None]:
        if not self.api_key:
            raise ValueError("未配置 API Key，请在设置中配置")

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.0,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        logger.info(
            "LLM请求 model=%s url=%s messages=%d tools=%s",
            self.model, url, len(messages),
            len(tools) if tools else 0,
        )

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST", url, headers=headers, json=body,
                ) as resp:
                    if resp.status_code != 200:
                        body_text = ""
                        async for chunk in resp.aiter_bytes():
                            body_text += chunk.decode(errors="replace")
                        logger.error(
                            "LLM响应错误 status=%d body=%s",
                            resp.status_code, body_text[:1000],
                        )
                        raise httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}",
                            request=resp.request, response=resp,
                        )
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"]
                            yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            if data.strip():
                                logger.warning("LLM chunk解析失败: %s", data[:200])
                            continue
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.error("LLM请求异常: %s", e, exc_info=True)
            raise

        logger.info("LLM请求完成 model=%s", self.model)


def get_llm_provider() -> LLMProvider:
    provider = get_setting("provider", "deepseek")
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])
    env_prefix = defaults["env_prefix"]

    api_key = (
        get_setting("api_key", "")
        or os.environ.get(f"{env_prefix}_API_KEY", "")
    )
    base_url = (
        get_setting("base_url", "")
        or os.environ.get(f"{env_prefix}_BASE_URL", defaults["base_url"])
    )
    model = (
        get_setting("model", "")
        or os.environ.get(f"{env_prefix}_MODEL", defaults["default_model"])
    )

    logger.info(
        "初始化LLM provider=%s model=%s base_url=%s api_key=%s",
        provider, model, base_url,
        f"****{api_key[-4:]}" if len(api_key) > 4 else "(未设置)",
    )
    return OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model)

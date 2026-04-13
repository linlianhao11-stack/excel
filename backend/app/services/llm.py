from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx

from ..database import get_setting


class LLMProvider:
    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncGenerator[dict, None]:
        raise NotImplementedError
        yield  # noqa


class DeepSeekProvider(LLMProvider):
    def __init__(self):
        # 优先从数据库读取，回退到环境变量
        self.api_key = get_setting("api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = get_setting("base_url", "") or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = get_setting("model", "") or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncGenerator[dict, None]:
        if not self.api_key:
            raise ValueError("未配置 API Key，请在设置中配置")

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

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=body,
            ) as resp:
                resp.raise_for_status()
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
                        continue


def get_llm_provider() -> LLMProvider:
    return DeepSeekProvider()

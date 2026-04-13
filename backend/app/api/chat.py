from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.agent import run_agent
from .auth import get_current_user
from .files import uploaded_files
from .conversations import save_message, update_conversation_title, save_conversation_files

router = APIRouter(prefix="/api", tags=["chat"])


from typing import List, Optional


class ChatRequest(BaseModel):
    message: str
    file_ids: List[str]
    conversation_id: Optional[str] = None


@router.post("/chat")
async def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    # 查找文件
    files = []
    for fid in req.file_ids:
        if fid not in uploaded_files:
            return StreamingResponse(
                iter(
                    [f"data: {json.dumps({'type': 'error', 'message': f'文件不存在: {fid}'})}\n\n"]
                ),
                media_type="text/event-stream",
            )
        files.append(uploaded_files[fid])

    if not files:
        return StreamingResponse(
            iter(
                [f"data: {json.dumps({'type': 'error', 'message': '请先上传文件'})}\n\n"]
            ),
            media_type="text/event-stream",
        )

    conv_id = req.conversation_id

    async def event_stream():
        nonlocal conv_id
        try:
            # 保存用户消息
            if conv_id:
                save_message(conv_id, "user", content=req.message)
                # 如果是第一条消息，更新对话标题
                update_conversation_title(conv_id, req.message[:30])
                # 保存文件关联
                save_conversation_files(conv_id, files)

            # 收集 assistant 完整回复用于保存
            full_content = ""
            all_tool_calls = []
            output_path = None
            error_msg = None

            async for event in run_agent(req.message, files):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                if event["type"] == "text":
                    full_content += event.get("content", "")
                elif event["type"] == "tool_call":
                    all_tool_calls.append({
                        "name": event["name"],
                        "code": event["code"],
                    })
                elif event["type"] == "tool_result":
                    if all_tool_calls:
                        all_tool_calls[-1]["result"] = event.get("result", "")
                elif event["type"] == "done":
                    output_path = event.get("output_path")
                elif event["type"] == "error":
                    error_msg = event.get("message")

            # 保存 assistant 消息
            if conv_id:
                save_message(
                    conv_id,
                    "assistant",
                    content=full_content or None,
                    tool_calls=all_tool_calls or None,
                    output_path=output_path,
                    error=error_msg,
                )

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

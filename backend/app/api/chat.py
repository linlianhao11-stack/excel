from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.agent import run_agent
from .auth import get_current_user
from .files import uploaded_files
from .conversations import save_message, update_conversation_title, save_conversation_files
from .diff import pending_diffs, conversation_state

logger = logging.getLogger("excel-agent.chat")

router = APIRouter(prefix="/api", tags=["chat"])


from typing import List, Optional


class ChatRequest(BaseModel):
    message: str
    file_ids: List[str] = []
    image_ids: List[str] = []
    conversation_id: Optional[str] = None


@router.post("/chat")
async def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    # 查找文件：优先使用 conversation_state 中的最新文件
    state = conversation_state.get(req.conversation_id, {}) if req.conversation_id else {}

    if state.get("current_file"):
        # 跨任务：使用上一轮的输出文件
        files = [state["current_file"]]
    else:
        # 首次：使用上传的文件
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

    # 查找图片文件
    images = []
    for iid in req.image_ids:
        if iid in uploaded_files and uploaded_files[iid].get("type") == "image":
            images.append(uploaded_files[iid])

    # 没有文件时直接提示用户
    if not files and not images:
        async def no_file_stream():
            msg = "请先上传 Excel 文件，我才能帮你处理数据。"
            yield f"data: {json.dumps({'type': 'text', 'content': msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'output_path': None})}\n\n"
            if conv_id:
                save_message(conv_id, "user", content=req.message)
                update_conversation_title(conv_id, req.message[:30])
                save_message(conv_id, "assistant", content=msg)
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_file_stream(), media_type="text/event-stream")

    operation_history = state.get("operation_history", [])

    logger.info(
        "Chat请求 user=%s message=%s files=%d images=%d conv=%s history=%d",
        user.get("username"), req.message[:60],
        len(files), len(images), req.conversation_id,
        len(operation_history),
    )

    conv_id = req.conversation_id

    async def event_stream():
        nonlocal conv_id
        try:
            # 保存用户消息
            if conv_id:
                save_message(conv_id, "user", content=req.message)
                update_conversation_title(conv_id, req.message[:30])
                save_conversation_files(conv_id, files)

            # 收集 assistant 完整回复用于保存
            full_content = ""
            all_tool_calls = []
            output_path = None
            error_msg = None

            async for event in run_agent(
                req.message, files, images,
                operation_history=operation_history or None,
            ):
                # 拦截 diff_review 事件：存 messages 到 pending_diffs
                if event.get("type") == "diff_review":
                    if conv_id:
                        pending_diffs[conv_id] = {
                            "messages": event["messages"],
                            "diff": event["diff"],
                            "output_path": event["output_path"],
                            "input_path": event["input_path"],
                            "file_paths": event["file_paths"],
                            "files": event.get("files", files),
                            "user_message": req.message,
                            "retry_count": 0,
                        }
                    # 推给前端的事件不含 messages
                    frontend_event = {
                        "type": "diff_review",
                        "diff": event["diff"],
                    }
                    yield f"data: {json.dumps(frontend_event, ensure_ascii=False)}\n\n"
                else:
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
                elif event["type"] == "output_ready":
                    output_path = event.get("output_path")
                elif event["type"] == "done":
                    output_path = event.get("output_path") or output_path
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
            logger.error("Chat异常: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

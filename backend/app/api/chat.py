from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.agent import run_agent
from .files import uploaded_files

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    file_ids: list[str]


@router.post("/chat")
async def chat(req: ChatRequest):
    # 查找文件
    files = []
    for fid in req.file_ids:
        if fid not in uploaded_files:
            return StreamingResponse(
                iter(
                    [
                        f"data: {json.dumps({'type': 'error', 'message': f'文件不存在: {fid}'})}\n\n"
                    ]
                ),
                media_type="text/event-stream",
            )
        files.append(uploaded_files[fid])

    if not files:
        return StreamingResponse(
            iter(
                [
                    f"data: {json.dumps({'type': 'error', 'message': '请先上传文件'})}\n\n"
                ]
            ),
            media_type="text/event-stream",
        )

    async def event_stream():
        try:
            async for event in run_agent(req.message, files):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

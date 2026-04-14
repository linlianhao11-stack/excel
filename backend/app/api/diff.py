from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.agent import run_agent
from ..services.excel import generate_operation_summary, profile_excel
from .auth import get_current_user

logger = logging.getLogger("excel-agent.diff")

router = APIRouter(prefix="/api/diff", tags=["diff"])

# 待审批的 diff（内存字典，进程重启后丢失）
pending_diffs: dict[str, dict] = {}

# 对话级状态（操作历史 + 当前文件）
conversation_state: dict[str, dict] = {}


class ApproveRequest(BaseModel):
    conversation_id: str


class RejectRequest(BaseModel):
    conversation_id: str
    reason_type: str = "other"  # too_many | too_few | wrong | other
    reason_text: str = ""


REASON_LABELS = {
    "too_many": "改多了——有些不该改的被改了",
    "too_few": "改少了——还有些该改的没改到",
    "wrong": "改错了——改的方向/数值不对",
    "other": "",
}


@router.post("/approve")
async def approve_diff(req: ApproveRequest, user: dict = Depends(get_current_user)):
    """用户确认变更，返回下载路径"""
    conv_id = req.conversation_id
    if conv_id not in pending_diffs:
        return {"error": "未找到待审批的变更"}

    pending = pending_diffs.pop(conv_id)
    output_path = pending["output_path"]
    diff_data = pending["diff"]
    user_message = pending.get("user_message", "")

    # 生成操作摘要
    summary_text = generate_operation_summary(user_message, diff_data)

    # 更新对话级状态
    state = conversation_state.setdefault(conv_id, {
        "operation_history": [],
        "current_file": None,
    })
    state["operation_history"].append(summary_text)

    # 更新当前文件：output 变为下一轮的 input
    try:
        new_profile = profile_excel(output_path)
    except Exception as e:
        logger.warning("重新profile失败: %s", e)
        new_profile = {}

    state["current_file"] = {
        "file_id": f"result_{conv_id}_{len(state['operation_history'])}",
        "filename": output_path.rsplit("/", 1)[-1],
        "path": output_path,
        "type": "excel",
        "profile": new_profile,
    }

    logger.info("Diff审批通过 conv=%s output=%s history_len=%d",
                conv_id, output_path, len(state["operation_history"]))

    return {"output_path": output_path}


@router.post("/reject")
async def reject_diff(req: RejectRequest, user: dict = Depends(get_current_user)):
    """用户驳回变更，触发 LLM 重试"""
    conv_id = req.conversation_id
    if conv_id not in pending_diffs:
        return {"error": "未找到待审批的变更"}

    pending = pending_diffs[conv_id]

    # 检查重试次数
    retry_count = pending.get("retry_count", 0)
    if retry_count >= 3:
        return {"error": "已达最大重试次数（3次），请换个方式描述需求"}

    # 取出完整 messages 数组
    messages = pending["messages"]
    file_paths = pending["file_paths"]
    files = pending.get("files", [])

    # 拼接驳回反馈
    reason_label = REASON_LABELS.get(req.reason_type, "")
    reason_detail = req.reason_text or reason_label or "用户对结果不满意"
    feedback = f"用户驳回了上次的修改。原因：{reason_detail}\n请根据反馈重新修改。"
    messages.append({"role": "user", "content": feedback})

    # 保存重试次数和 user_message 供后续使用
    saved_retry_count = retry_count + 1
    saved_user_message = pending.get("user_message", "")

    # 清除旧的 pending_diffs，防止用户在重试期间 approve 旧结果
    pending_diffs.pop(conv_id, None)

    logger.info("Diff驳回 conv=%s retry=%d reason=%s", conv_id, saved_retry_count, reason_detail[:50])

    async def event_stream():
        try:
            async for event in run_agent(resume_messages=messages, files=files):
                # 拦截新的 diff_review 事件，更新 pending_diffs
                if event.get("type") == "diff_review":
                    pending_diffs[conv_id] = {
                        "messages": event["messages"],
                        "diff": event["diff"],
                        "output_path": event["output_path"],
                        "input_path": event["input_path"],
                        "file_paths": event["file_paths"],
                        "files": event.get("files", files),
                        "user_message": saved_user_message,
                        "retry_count": saved_retry_count,
                    }
                    # 推给前端的事件不含 messages（太大）
                    frontend_event = {
                        "type": "diff_review",
                        "diff": event["diff"],
                    }
                    yield f"data: {json.dumps(frontend_event, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("Reject重试异常: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

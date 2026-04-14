from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
from pathlib import Path
from typing import AsyncGenerator

from .llm import get_llm_provider
from .sandbox import execute_code, execute_query
from .excel import build_context, compute_diff, compute_create_summary

logger = logging.getLogger("excel-agent.agent")


class LoopGuard:
    """Agent 循环护栏：防止重复调用、过度探索、无限循环"""
    def __init__(self, max_turns=25, max_same_tool=3, max_consecutive_query=8):
        self.max_turns = max_turns
        self.max_same_tool = max_same_tool
        self.max_consecutive_query = max_consecutive_query
        self.turn = 0
        self.tool_signatures: dict[str, int] = {}
        self.consecutive_query = 0

    def on_turn(self) -> str | None:
        self.turn += 1
        if self.turn > self.max_turns:
            return f"已达到最大轮数 ({self.max_turns})"
        return None

    def on_tool_call(self, name: str, code: str) -> str | None:
        sig = hashlib.md5(f"{name}:{code}".encode()).hexdigest()
        self.tool_signatures[sig] = self.tool_signatures.get(sig, 0) + 1
        if self.tool_signatures[sig] > self.max_same_tool:
            return f"相同工具调用已重复 {self.max_same_tool} 次"
        if name == "query":
            self.consecutive_query += 1
            if self.consecutive_query > self.max_consecutive_query:
                return f"连续探索已达 {self.max_consecutive_query} 次，请开始执行"
        else:
            self.consecutive_query = 0
        return None


def classify_error(stderr: str) -> tuple[str, bool]:
    s = stderr.lower()
    if "执行超时" in stderr or "timeoutexpired" in s:
        return ("timeout", False)
    if "memoryerror" in s or "killed" in s:
        return ("memory", False)
    if "安全检查失败" in stderr:
        return ("safety", True)
    if "filenotfounderror" in s:
        return ("file_not_found", True)
    if "syntaxerror" in s:
        return ("syntax", True)
    if "modify 模式禁止" in stderr:
        return ("safety", True)
    return ("code_error", True)


class ErrorTracker:
    def __init__(self, max_per_type=3):
        self.max_per_type = max_per_type
        self.counts: dict[str, int] = {}

    def record(self, stderr: str) -> tuple[str, bool, bool]:
        error_type, is_retryable = classify_error(stderr)
        self.counts[error_type] = self.counts.get(error_type, 0) + 1
        limit_reached = self.counts[error_type] >= self.max_per_type
        return error_type, is_retryable, limit_reached


SYSTEM_PROMPT = """你是一个 Excel 数据处理助手。用户会上传 Excel 文件并描述处理需求。

## 可用工具

1. **query** — 执行只读 Python 代码探索数据（查看内容、统计、筛选等）
   代码中可用变量: INPUT_PATH_1, INPUT_PATH_2, ...
   用 print() 输出你想看的内容

2. **modify** — 修改现有 Excel 文件，保留原始格式
   系统已自动将原文件复制到 OUTPUT_PATH，你只需要用 openpyxl 修改需要改的单元格。
   代码中可用变量: INPUT_PATH_1, INPUT_PATH_2, ..., OUTPUT_PATH
   **禁止使用 pandas 写文件**（to_excel/to_csv/ExcelWriter 会被系统拦截）。
   用 openpyxl 的 load_workbook(OUTPUT_PATH) 打开并修改，最后 wb.save(OUTPUT_PATH)。
   如果要修改的不是第一个文件，用 source 参数指定（如 "INPUT_PATH_2"）。

3. **create** — 生成全新的 Excel 文件
   代码中可用变量: INPUT_PATH_1, INPUT_PATH_2, ..., OUTPUT_PATH
   可以使用 pandas 或 openpyxl，结果写入 OUTPUT_PATH。
   **仅用于从零生成新文件**（汇总表、合并表、新报表等）。
   如果你需要读取并修改现有文件的内容，必须用 modify 而不是 create。

可用的库: pandas, numpy, re, datetime, openpyxl, copy, shutil
禁止使用: os, sys, subprocess 等系统模块

## 工作纪律

**边做边说：**
- 每次调用工具前，用一句话说明你要做什么、为什么（例如："我先看一下A列的空值分布"）
- 工具执行后，用文字简要解读结果，再决定下一步

**高效探索：**
- 不要重复执行相同的 query
- 每次 query 要有明确目的，不要盲目 print 整个 DataFrame
- 需要的信息尽量合并到一次 query 中获取

**谨慎修改：**
- 涉及批量修改、删除行、改公式时，先描述你的方案
- 只修改需要改的单元格，不要整列覆写

**任务不明确时主动澄清：**
- 如果用户的需求模糊或有歧义，先问清楚再动手

## 完成规则

modify 或 create 成功后，你的任务就完成了。不要再调用任何工具。
系统会自动对比输入输出文件并生成变更报告展示给用户。"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query",
            "description": "执行只读 Python 代码探索数据，返回 print 输出",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify",
            "description": "修改现有 Excel 文件并保留原始格式。系统已自动复制原文件到 OUTPUT_PATH，用 openpyxl 修改即可。禁止使用 pandas 写文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码（使用 openpyxl）",
                    },
                    "source": {
                        "type": "string",
                        "description": "要修改的文件变量名，默认 INPUT_PATH_1",
                        "default": "INPUT_PATH_1",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create",
            "description": "生成全新的 Excel 文件到 OUTPUT_PATH。可以使用 pandas 或 openpyxl。仅用于从零生成新文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码",
                    }
                },
                "required": ["code"],
            },
        },
    },
]

INTERRUPTED_PROMPT = (
    "任务被系统中断，原因：{reason}。\n"
    "请根据你已经完成的工作，用中文如实总结当前进度：已完成了什么、还有什么没做完、"
    "用户接下来应该怎么操作。不要编造未完成的工作结果。"
    "{output_info}"
)


def _build_image_content(images: list[dict]) -> list[dict]:
    """将图片文件转为 OpenAI vision 格式的 content 块"""
    parts = []
    for img in images:
        img_path = Path(img["path"])
        if not img_path.exists():
            continue
        data = base64.b64encode(img_path.read_bytes()).decode()
        media_type = mimetypes.guess_type(img["filename"])[0] or "image/png"
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{data}"},
        })
    return parts


async def _generate_interrupted_summary(llm, messages, reason, output_path):
    output_info = ""
    if output_path:
        output_info = "\n\n注意：之前有一次操作成功生成了文件，该文件可供用户下载，但后续操作可能未完成。"
    msg = INTERRUPTED_PROMPT.format(reason=reason, output_info=output_info)
    messages.append({"role": "user", "content": msg})
    async for delta in llm.chat_stream(messages, tools=None):
        if delta.get("content"):
            yield {"type": "text", "content": delta["content"]}
    yield {"type": "done", "output_path": output_path}


async def run_agent(
    user_message: str = None,
    files: list = None,
    images: list = None,
    operation_history: list[str] = None,
    resume_messages: list[dict] = None,
):
    """Agent 主循环。

    正常调用：传 user_message + files
    驳回重试：传 resume_messages（含完整上下文），跳过初始化
    """
    llm = get_llm_provider()
    files = files or []
    images = images or []

    if resume_messages:
        # 驳回重试：直接使用传入的 messages
        messages = resume_messages
        # 从 messages 中提取 file_paths（存在 system prompt 中的变量引用）
        excel_files = [f for f in files if f.get("type") != "image"]
        file_paths = {}
        for i, f in enumerate(excel_files, 1):
            file_paths[f"INPUT_PATH_{i}"] = f["path"]
        logger.info("Agent重试 messages_len=%d files=%d", len(messages), len(files))
    else:
        # 正常启动
        logger.info("Agent启动 message=%s files=%d images=%d",
                     (user_message or "")[:80], len(files), len(images))

        excel_files = [f for f in files if f.get("type") != "image"]
        file_paths = {}
        for i, f in enumerate(excel_files, 1):
            file_paths[f"INPUT_PATH_{i}"] = f["path"]

        context = build_context(files)

        # 构建 user message，含历史操作摘要
        parts = []
        if context:
            parts.append(f"已上传的文件信息：\n\n{context}")
        if operation_history:
            history_text = "历史操作：\n"
            for i, op in enumerate(operation_history, 1):
                history_text += f"{i}. {op}\n"
            parts.append(history_text)
        parts.append(f"本次需求：{user_message}" if operation_history else f"用户需求：{user_message}")
        user_text = "\n\n".join(parts)

        if images:
            user_content = [{"type": "text", "text": user_text}]
            user_content.extend(_build_image_content(images))
        else:
            user_content = user_text

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

    guard = LoopGuard()
    errors = ErrorTracker()
    output_path = None

    while True:
        reason = guard.on_turn()
        if reason:
            logger.warning("LoopGuard 终止: %s", reason)
            yield {"type": "phase", "name": "reporting"}
            async for evt in _generate_interrupted_summary(llm, messages, reason, output_path):
                yield evt
            return

        logger.info("Agent turn=%d/%d", guard.turn, guard.max_turns)

        full_content = ""
        tool_calls_data = {}
        current_tool_id = None

        try:
            async for delta in llm.chat_stream(messages, tools=TOOLS if file_paths else None):
                if delta.get("content"):
                    full_content += delta["content"]
                    yield {"type": "text", "content": delta["content"]}
                if "tool_calls" in delta:
                    for tc in delta["tool_calls"]:
                        tc_id = tc.get("id")
                        if tc_id:
                            current_tool_id = tc_id
                            tool_calls_data[tc_id] = {"name": tc["function"]["name"], "arguments_str": ""}
                        if current_tool_id and "function" in tc:
                            args_chunk = tc["function"].get("arguments", "")
                            if args_chunk:
                                tool_calls_data[current_tool_id]["arguments_str"] += args_chunk
        except Exception as e:
            logger.error("LLM 调用失败: %s", e, exc_info=True)
            yield {"type": "error", "message": f"LLM 调用失败: {e}"}
            yield {"type": "done", "output_path": None}
            return

        if not tool_calls_data:
            logger.info("Agent完成 turn=%d output=%s", guard.turn, output_path)
            yield {"type": "done", "output_path": output_path}
            return

        assistant_msg = {"role": "assistant", "content": full_content or None, "tool_calls": []}
        for tc_id, tc_info in tool_calls_data.items():
            assistant_msg["tool_calls"].append({
                "id": tc_id, "type": "function",
                "function": {"name": tc_info["name"], "arguments": tc_info["arguments_str"]},
            })
        messages.append(assistant_msg)

        for tc_id, tc_info in tool_calls_data.items():
            name = tc_info["name"]
            try:
                args = json.loads(tc_info["arguments_str"])
            except json.JSONDecodeError:
                tool_result = "参数解析失败"
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_result})
                yield {"type": "tool_result", "name": name, "result": tool_result}
                continue

            code = args.get("code", "")

            reason = guard.on_tool_call(name, code)
            if reason:
                logger.warning("LoopGuard 拦截工具调用: %s", reason)
                for remaining_id in tool_calls_data:
                    messages.append({"role": "tool", "tool_call_id": remaining_id, "content": f"系统中断: {reason}"})
                yield {"type": "tool_result", "name": name, "result": f"系统中断: {reason}"}
                yield {"type": "phase", "name": "reporting"}
                async for evt in _generate_interrupted_summary(llm, messages, reason, output_path):
                    yield evt
                return

            logger.info("工具调用 name=%s code_len=%d", name, len(code))
            yield {"type": "tool_call", "name": name, "code": code}

            if name == "query":
                result = await execute_query(code, file_paths)
                tool_result = result["output"] if result["success"] else f"错误: {result['output']}"
                logger.info("query结果 success=%s output_len=%d", result["success"], len(tool_result))

            elif name == "modify":
                source = args.get("source", "INPUT_PATH_1")
                source_path = file_paths.get(source)
                if not source_path:
                    tool_result = f"错误: 未找到文件 {source}，可用文件: {list(file_paths.keys())}"
                    messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_result})
                    yield {"type": "tool_result", "name": name, "result": tool_result}
                    continue

                result = await execute_code(
                    code, file_paths,
                    mode="modify",
                    pre_copy_from=source_path,
                )
                if result["success"]:
                    output_path = result["output_path"]
                    tool_result = "修改成功。输出文件已生成。"
                    if result["stdout"]:
                        tool_result += f"\n标准输出: {result['stdout']}"
                    logger.info("modify成功 output=%s", output_path)

                    messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_result})
                    yield {"type": "tool_result", "name": name, "result": tool_result}

                    # 进入 diff 审查流程
                    yield {"type": "phase", "name": "verifying"}
                    try:
                        diff_data = compute_diff(source_path, output_path)
                    except Exception as e:
                        logger.error("diff计算失败: %s", e, exc_info=True)
                        diff_data = {"summary": {}, "integrity": {}, "changes": [], "error": str(e)}

                    yield {
                        "type": "diff_review",
                        "diff": diff_data,
                        "output_path": output_path,
                        "input_path": source_path,
                        "messages": messages,
                        "file_paths": file_paths,
                        "files": files,
                    }
                    yield {"type": "done", "output_path": None}
                    return
                else:
                    error_type, is_retryable, limit_reached = errors.record(result["stderr"])
                    logger.warning("modify失败 type=%s retryable=%s limit=%s", error_type, is_retryable, limit_reached)
                    if not is_retryable:
                        yield {"type": "error", "message": f"不可恢复的错误 ({error_type}): {result['stderr'][:300]}"}
                        yield {"type": "done", "output_path": None}
                        return
                    if limit_reached:
                        yield {"type": "error", "message": f"{error_type} 错误已重试 {errors.max_per_type} 次仍失败: {result['stderr'][:300]}"}
                        yield {"type": "done", "output_path": None}
                        return
                    tool_result = f"执行失败 ({error_type}): {result['stderr']}"

            elif name == "create":
                result = await execute_code(code, file_paths, mode="create")
                if result["success"]:
                    output_path = result["output_path"]
                    tool_result = "创建成功。输出文件已生成。"
                    if result["stdout"]:
                        tool_result += f"\n标准输出: {result['stdout']}"
                    logger.info("create成功 output=%s", output_path)

                    messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_result})
                    yield {"type": "tool_result", "name": name, "result": tool_result}

                    # create 流程：生成摘要 + 直接可下载
                    yield {"type": "phase", "name": "verifying"}
                    try:
                        summary_data = compute_create_summary(output_path)
                    except Exception as e:
                        logger.error("摘要生成失败: %s", e, exc_info=True)
                        summary_data = {"error": str(e)}

                    yield {"type": "create_summary", "summary": summary_data}
                    yield {"type": "output_ready", "output_path": output_path}
                    yield {"type": "done", "output_path": output_path}
                    return
                else:
                    error_type, is_retryable, limit_reached = errors.record(result["stderr"])
                    logger.warning("create失败 type=%s retryable=%s limit=%s", error_type, is_retryable, limit_reached)
                    if not is_retryable:
                        yield {"type": "error", "message": f"不可恢复的错误 ({error_type}): {result['stderr'][:300]}"}
                        yield {"type": "done", "output_path": None}
                        return
                    if limit_reached:
                        yield {"type": "error", "message": f"{error_type} 错误已重试 {errors.max_per_type} 次仍失败: {result['stderr'][:300]}"}
                        yield {"type": "done", "output_path": None}
                        return
                    tool_result = f"执行失败 ({error_type}): {result['stderr']}"

            else:
                tool_result = f"未知工具: {name}"

            messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_result})
            yield {"type": "tool_result", "name": name, "result": tool_result}

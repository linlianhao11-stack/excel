# Excel Agent 优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 Agent 的系统提示词、循环控制、错误处理、自动验证、变更报告和前端状态展示，解决无限循环、无报告输出、UI 状态断层等问题。

**Architecture:** 三层优化 — 系统提示词（引导层）+ Agent 代码护栏（保障层）+ 前端状态机（展示层）。核心改动在 `agent.py`（LoopGuard + 强制报告模式 + 自动验证 + 错误分类），前端 `useChat.js` 和 `ChatPanel.vue` 配合状态机升级。

**Tech Stack:** Python/FastAPI (backend), Vue 3 Composition API (frontend), SSE streaming

**设计文档:** `docs/superpowers/specs/2026-04-14-agent-optimization-design.md`

---

### Task 1: LoopGuard 类

**Files:**
- Modify: `backend/app/services/agent.py` (文件顶部，SYSTEM_PROMPT 之前)

- [ ] **Step 1: 在 agent.py 中添加 LoopGuard 类**

在 `import` 块之后、`SYSTEM_PROMPT` 之前添加：

```python
import hashlib


class LoopGuard:
    """Agent 循环护栏：防止重复调用、过度探索、无限循环"""

    def __init__(self, max_turns=25, max_same_tool=3, max_consecutive_query=8):
        self.max_turns = max_turns
        self.max_same_tool = max_same_tool
        self.max_consecutive_query = max_consecutive_query
        self.turn = 0
        self.tool_signatures: dict[str, int] = {}  # hash -> count
        self.consecutive_query = 0

    def on_turn(self) -> str | None:
        self.turn += 1
        if self.turn > self.max_turns:
            return f"已达到最大轮数 ({self.max_turns})"
        return None

    def on_tool_call(self, name: str, code: str) -> str | None:
        # 重复签名检测
        sig = hashlib.md5(f"{name}:{code}".encode()).hexdigest()
        self.tool_signatures[sig] = self.tool_signatures.get(sig, 0) + 1
        if self.tool_signatures[sig] > self.max_same_tool:
            return f"相同工具调用已重复 {self.max_same_tool} 次"

        # 连续 query 检测
        if name == "query":
            self.consecutive_query += 1
            if self.consecutive_query > self.max_consecutive_query:
                return f"连续探索已达 {self.max_consecutive_query} 次，请开始执行"
        else:
            self.consecutive_query = 0

        return None
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/agent.py
git commit -m "feat(agent): add LoopGuard class for loop detection"
```

---

### Task 2: 错误分类器

**Files:**
- Modify: `backend/app/services/agent.py` (LoopGuard 类之后)

- [ ] **Step 1: 添加错误分类函数和 ErrorTracker 类**

在 LoopGuard 类之后添加：

```python
def classify_error(stderr: str) -> tuple[str, bool]:
    """分类执行错误。返回 (error_type, is_retryable)"""
    s = stderr.lower()
    if "执行超时" in stderr or "timeoutexpired" in s:
        return ("timeout", False)
    if "memoryerror" in s or "killed" in s:
        return ("memory", False)
    if "安全检查失败" in stderr:
        return ("safety", False)
    if "filenotfounderror" in s:
        return ("file_not_found", True)
    if "syntaxerror" in s:
        return ("syntax", True)
    # 默认：代码逻辑错误，可重试
    return ("code_error", True)


class ErrorTracker:
    """按错误类型独立计数"""

    def __init__(self, max_per_type=3):
        self.max_per_type = max_per_type
        self.counts: dict[str, int] = {}

    def record(self, stderr: str) -> tuple[str, bool, bool]:
        """记录错误，返回 (error_type, is_retryable, limit_reached)"""
        error_type, is_retryable = classify_error(stderr)
        self.counts[error_type] = self.counts.get(error_type, 0) + 1
        limit_reached = self.counts[error_type] >= self.max_per_type
        return error_type, is_retryable, limit_reached
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/agent.py
git commit -m "feat(agent): add error classifier and ErrorTracker"
```

---

### Task 3: 自动验证函数

**Files:**
- Modify: `backend/app/services/agent.py` (ErrorTracker 之后)

- [ ] **Step 1: 添加验证代码生成函数**

```python
def _read_file_code(var_name: str, path: str) -> str:
    """生成读取单个文件的代码片段，自动区分 CSV 和 Excel"""
    safe_p = path.replace("\\", "\\\\").replace('"', '\\"')
    if path.lower().endswith(".csv"):
        return (
            f'{var_name}_sheets = {{}}\n'
            f'try:\n'
            f'    _df = pd.read_csv("{safe_p}")\n'
            f'    {var_name}_sheets["Sheet1"] = {{"rows": len(_df), "cols": len(_df.columns), '
            f'"nulls": int(_df.isnull().sum().sum()), "col_nulls": _df.isnull().sum().to_dict(), '
            f'"sample": _df.head(3).to_string()}}\n'
            f'except Exception as e:\n'
            f'    report.append(f"{var_name} 读取失败: {{e}}")\n'
        )
    return (
        f'{var_name}_sheets = {{}}\n'
        f'try:\n'
        f'    for _s in pd.ExcelFile("{safe_p}").sheet_names:\n'
        f'        _df = pd.read_excel("{safe_p}", sheet_name=_s)\n'
        f'        {var_name}_sheets[_s] = {{"rows": len(_df), "cols": len(_df.columns), '
        f'"nulls": int(_df.isnull().sum().sum()), "col_nulls": _df.isnull().sum().to_dict(), '
        f'"sample": _df.head(3).to_string()}}\n'
        f'except Exception as e:\n'
        f'    report.append(f"{var_name} 读取失败: {{e}}")\n'
    )


def build_verification_code(file_paths: dict[str, str], output_path: str) -> str:
    """生成对比输入/输出文件的验证脚本。兼容 CSV 和 Excel，按 (文件名, sheet) 维度对比。"""
    safe_out = output_path.replace("\\", "\\\\").replace('"', '\\"')

    parts = ["import pandas as pd", "", "report = []", ""]

    # 读输出文件
    parts.append(_read_file_code("output", output_path))

    # 读每个输入文件
    for var, path in file_paths.items():
        parts.append(_read_file_code(var, path))

    # 统计每个 sheet 被几个输入引用（用于标注近似比较）
    parts.append("_sheet_ref_count = {}")
    for var in file_paths:
        parts.append(f'for _s in {var}_sheets:')
        parts.append(f'    _sheet_ref_count[_s] = _sheet_ref_count.get(_s, 0) + 1')
    parts.append("")

    # 对比逻辑：按 (输入文件, sheet) 维度逐个比较
    parts.append("# 逐文件逐 sheet 对比")
    for var in file_paths:
        parts.append(f'for _s, _in in {var}_sheets.items():')
        parts.append(f'    _label = f"[{var}] Sheet [{{_s}}]"')
        parts.append(f'    if _sheet_ref_count.get(_s, 0) > 1:')
        parts.append(f'        _label += " (多个输入共享此输出 sheet，以下为近似对比)"')
        parts.append(f'    report.append(f"\\n{{_label}}:")')
        parts.append(f'    if _s in output_sheets:')
        parts.append(f'        _out = output_sheets[_s]')
        parts.append(f'        report.append(f"  行数: {{_in[\\"rows\\"]}} → {{_out[\\"rows\\"]}}")')
        parts.append(f'        report.append(f"  列数: {{_in[\\"cols\\"]}} → {{_out[\\"cols\\"]}}")')
        parts.append(f'        report.append(f"  空值: {{_in[\\"nulls\\"]}} → {{_out[\\"nulls\\"]}}")')
        # 逐列空值变化
        parts.append(f'        for _c in _in["col_nulls"]:')
        parts.append(f'            _before = _in["col_nulls"][_c]')
        parts.append(f'            _after = _out.get("col_nulls", {{}}).get(_c, "N/A")')
        parts.append(f'            if _before != _after:')
        parts.append(f'                report.append(f"    列[{{_c}}] 空值: {{_before}} → {{_after}}")')
        # 异常警告
        parts.append(f'        if _out["rows"] < _in["rows"] * 0.5:')
        parts.append(f'            report.append("  ⚠ 警告: 行数减少超过50%")')
        parts.append(f'        if _out["nulls"] > _in["nulls"] * 2 and _out["nulls"] - _in["nulls"] > 10:')
        parts.append(f'            report.append(f"  ⚠ 警告: 空值大幅增加")')
        # before/after 抽样对比
        parts.append(f'        report.append(f"  输入前3行:")')
        parts.append(f'        report.append(_in["sample"])')
        parts.append(f'        report.append(f"  输出前3行:")')
        parts.append(f'        report.append(_out["sample"])')
        parts.append(f'    else:')
        parts.append(f'        report.append(f"  (输出中无此 sheet)")')
        parts.append("")

    # 输出中新增的 sheet
    parts.append('_all_input_sheets = set()')
    for var in file_paths:
        parts.append(f'_all_input_sheets.update({var}_sheets.keys())')
    parts.append('for _s in output_sheets:')
    parts.append('    if _s not in _all_input_sheets:')
    parts.append('        report.append(f"\\n[新增 sheet] [{_s}]: {output_sheets[_s][\\"rows\\"]}行x{output_sheets[_s][\\"cols\\"]}列")')
    parts.append('        report.append(output_sheets[_s]["sample"])')
    parts.append("")
    parts.append('print("\\n".join(report))')

    return "\n".join(parts)
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/agent.py
git commit -m "feat(agent): add auto-verification code builder"
```

---

### Task 4: 重写系统提示词

**Files:**
- Modify: `backend/app/services/agent.py` — 替换 `SYSTEM_PROMPT` 变量

- [ ] **Step 1: 替换 SYSTEM_PROMPT**

将现有 `SYSTEM_PROMPT = """..."""` 整段替换为：

```python
SYSTEM_PROMPT = """你是一个 Excel 数据处理助手。用户会上传 Excel 文件并描述处理需求。

## 可用工具

1. **query** — 执行只读 Python 代码探索数据（查看内容、统计、筛选等）
   代码中可用变量: INPUT_PATH_1, INPUT_PATH_2, ...
   用 print() 输出你想看的内容

2. **execute** — 执行 Python 代码处理数据并生成结果文件
   代码中可用变量: INPUT_PATH_1, INPUT_PATH_2, ..., OUTPUT_PATH
   必须将结果写入 OUTPUT_PATH（.xlsx 格式）

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
- 修改现有文件时用 openpyxl（先 shutil.copy2 复制原文件到 OUTPUT_PATH，再修改副本），不要用 pandas 写文件（会丢失格式、合并单元格、公式、样式）

**任务不明确时主动澄清：**
- 如果用户的需求模糊或有歧义，先问清楚再动手

## 完成规则

execute 成功后，你的任务就完成了。不要再调用任何工具。
系统会自动验证结果并把验证信息提供给你，届时请直接用中文输出变更报告，涵盖：
- 做了哪些修改
- 具体怎么改的（涉及哪些 sheet、列、行范围）
- 为什么这么改
- 可能存在的风险、边界情况、未处理的异常数据"""
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/agent.py
git commit -m "feat(agent): rewrite system prompt with phased workflow and interaction discipline"
```

---

### Task 5: 重写 run_agent 主循环

**Files:**
- Modify: `backend/app/services/agent.py` — 替换 `run_agent` 函数

这是最核心的改动，整合 LoopGuard、ErrorTracker、强制报告模式、自动验证、阶段事件。

- [ ] **Step 1: 替换 run_agent 函数**

删除现有的 `MAX_TURNS`、`MAX_RETRIES` 常量和整个 `run_agent` 函数，替换为：

```python
REPORT_PROMPT = (
    "execute 已成功，系统已自动对比输入输出文件。请根据以下验证信息和你之前的操作，"
    "用中文自然语言段落输出变更报告。涵盖：做了什么修改、怎么改的、为什么这么改、"
    "有什么风险或注意事项。\n\n验证结果：\n{verification}"
)

INTERRUPTED_PROMPT = (
    "任务被系统中断，原因：{reason}。\n"
    "请根据你已经完成的工作，用中文如实总结当前进度：已完成了什么、还有什么没做完、"
    "用户接下来应该怎么操作。不要编造未完成的工作结果。"
    "{output_info}"
)


async def _generate_report(
    llm,
    messages: list[dict],
    verification: str,
    output_path: str,
) -> AsyncGenerator[dict, None]:
    """强制报告模式（execute 成功后）：不传 tools，LLM 只能输出文字"""
    report_msg = REPORT_PROMPT.format(verification=verification or "验证跳过")
    messages.append({"role": "user", "content": report_msg})

    async for delta in llm.chat_stream(messages, tools=None):
        if delta.get("content"):
            yield {"type": "text", "content": delta["content"]}

    yield {"type": "done", "output_path": output_path}


async def _generate_interrupted_summary(
    llm,
    messages: list[dict],
    reason: str,
    output_path: str | None,
) -> AsyncGenerator[dict, None]:
    """中断总结模式（LoopGuard/致命错误触发）：如实总结进度，不编造结果"""
    output_info = ""
    if output_path:
        output_info = f"\n\n注意：之前有一次 execute 成功生成了文件，该文件可供用户下载，但后续操作可能未完成。"
    msg = INTERRUPTED_PROMPT.format(reason=reason, output_info=output_info)
    messages.append({"role": "user", "content": msg})

    async for delta in llm.chat_stream(messages, tools=None):
        if delta.get("content"):
            yield {"type": "text", "content": delta["content"]}

    yield {"type": "done", "output_path": output_path}


async def run_agent(
    user_message: str,
    files: list[dict],
    images: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """Agent 主循环"""
    llm = get_llm_provider()
    images = images or []

    logger.info("Agent启动 message=%s files=%d images=%d", user_message[:80], len(files), len(images))

    # 构建文件路径映射
    excel_files = [f for f in files if f.get("type") != "image"]
    file_paths = {}
    for i, f in enumerate(excel_files, 1):
        file_paths[f"INPUT_PATH_{i}"] = f["path"]

    # 构建初始消息
    context = build_context(files)
    user_text = f"已上传的文件信息：\n\n{context}\n\n用户需求：{user_message}" if context else user_message
    if images:
        user_content: list | str = [{"type": "text", "text": user_text}]
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
        # LoopGuard 检查轮数
        reason = guard.on_turn()
        if reason:
            logger.warning("LoopGuard 终止: %s", reason)
            yield {"type": "phase", "name": "reporting"}
            async for evt in _generate_interrupted_summary(llm, messages, reason, output_path):
                yield evt
            return

        logger.info("Agent turn=%d/%d", guard.turn, guard.max_turns)

        # LLM 调用
        full_content = ""
        tool_calls_data: dict[str, dict] = {}
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

        # 没有工具调用 → 对话自然结束
        if not tool_calls_data:
            logger.info("Agent完成 turn=%d output=%s", guard.turn, output_path)
            yield {"type": "done", "output_path": output_path}
            return

        # 构建 assistant 消息
        assistant_msg = {"role": "assistant", "content": full_content or None, "tool_calls": []}
        for tc_id, tc_info in tool_calls_data.items():
            assistant_msg["tool_calls"].append({
                "id": tc_id, "type": "function",
                "function": {"name": tc_info["name"], "arguments": tc_info["arguments_str"]},
            })
        messages.append(assistant_msg)

        # 执行工具
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

            # LoopGuard 检查工具调用
            reason = guard.on_tool_call(name, code)
            if reason:
                logger.warning("LoopGuard 拦截工具调用: %s", reason)
                # 补齐所有 pending tool_call 的 response（OpenAI API 要求每个 tool_call 都有对应 tool message）
                for remaining_id, remaining_info in tool_calls_data.items():
                    messages.append({"role": "tool", "tool_call_id": remaining_id, "content": f"系统中断: {reason}"})
                yield {"type": "tool_result", "name": name, "result": f"系统中断: {reason}"}
                # 硬收口：直接进入中断总结，不再回到主循环
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

            elif name == "execute":
                result = await execute_code(code, file_paths)
                if result["success"]:
                    output_path = result["output_path"]
                    tool_result = "执行成功。输出文件已生成。"
                    if result["stdout"]:
                        tool_result += f"\n标准输出: {result['stdout']}"
                    logger.info("execute成功 output=%s", output_path)
                    yield {"type": "output_ready", "output_path": output_path}

                    # === 强制报告模式 ===
                    messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_result})
                    yield {"type": "tool_result", "name": name, "result": tool_result}

                    # 自动验证
                    yield {"type": "phase", "name": "verifying"}
                    verification = ""
                    if file_paths and output_path:
                        verify_code = build_verification_code(file_paths, output_path)
                        verify_result = await execute_query(verify_code, {})
                        verification = verify_result["output"] if verify_result["success"] else f"验证脚本出错: {verify_result['output']}"
                        logger.info("自动验证完成: %s", verification[:200])

                    # 进入报告阶段
                    yield {"type": "phase", "name": "reporting"}
                    async for evt in _generate_report(llm, messages, verification, output_path):
                        yield evt
                    return
                else:
                    # 错误分类处理
                    error_type, is_retryable, limit_reached = errors.record(result["stderr"])
                    logger.warning("execute失败 type=%s retryable=%s limit=%s", error_type, is_retryable, limit_reached)

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
```

- [ ] **Step 2: 删除旧常量**

确保删除文件中旧的 `MAX_TURNS = 100` 和 `MAX_RETRIES = 3` 行（已被 LoopGuard 和 ErrorTracker 替代）。

- [ ] **Step 3: 提交**

```bash
git add backend/app/services/agent.py
git commit -m "feat(agent): rewrite run_agent with LoopGuard, forced report, auto-verification, error classification"
```

---

### Task 6: 更新 chat.py 事件处理

**Files:**
- Modify: `backend/app/api/chat.py`

- [ ] **Step 1: 在 event_stream 中追踪 phase 和 output_ready 事件**

在 `chat.py` 的 `event_stream` 函数中，确保 `output_ready` 和 `phase` 事件被正确处理。找到事件处理的 `if/elif` 链，替换为：

```python
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
                # phase 事件只需流式转发，不需记录
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/api/chat.py
git commit -m "feat(chat): handle output_ready and phase events"
```

---

### Task 7: 前端状态机 — useChat.js

**Files:**
- Modify: `frontend/src/composables/useChat.js`

- [ ] **Step 1: 将 `thinking` 替换为 `status` 状态机**

全量替换 `useChat.js` 内容：

```javascript
import { ref, reactive } from 'vue'
import { chatStream } from '../api'

const messages = ref([])
const streaming = ref(false)
const status = ref(null) // null | 'thinking' | 'running' | 'verifying' | 'reporting'
let controller = null

export function useChat() {
  function send(text, fileIds, conversationId, imageIds = []) {
    const userMsg = { id: Date.now(), role: 'user', content: text }
    if (imageIds.length > 0) {
      const token = localStorage.getItem('token')
      userMsg.images = imageIds.map(id => `/api/files/${id}/image?token=${encodeURIComponent(token)}`)
    }
    messages.value.push(userMsg)

    const assistantMsg = reactive({
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      toolCalls: [],
      outputPath: null,
      error: null,
    })
    messages.value.push(assistantMsg)

    streaming.value = true
    status.value = 'thinking'

    controller = chatStream(
      text, fileIds, conversationId,
      (event) => {
        switch (event.type) {
          case 'text':
            status.value = null
            assistantMsg.content += event.content
            break
          case 'tool_call':
            status.value = 'running'
            assistantMsg.toolCalls.push(reactive({
              name: event.name,
              code: event.code,
              result: null,
              expanded: false,
            }))
            break
          case 'tool_result': {
            status.value = 'thinking'
            const lastCall = assistantMsg.toolCalls[assistantMsg.toolCalls.length - 1]
            if (lastCall) lastCall.result = event.result
            break
          }
          case 'phase':
            status.value = event.name // 'verifying' | 'reporting'
            break
          case 'output_ready':
            assistantMsg.outputPath = event.output_path
            break
          case 'done':
            status.value = null
            assistantMsg.outputPath = event.output_path || assistantMsg.outputPath
            streaming.value = false
            break
          case 'error':
            status.value = null
            assistantMsg.error = event.message
            streaming.value = false
            break
          case 'stream_end':
            status.value = null
            streaming.value = false
            break
        }
      },
      imageIds,
    )
  }

  function stop() {
    if (controller) controller.abort()
    streaming.value = false
    status.value = null
  }

  function clearMessages() {
    messages.value = []
    status.value = null
  }

  function loadFromHistory(historyMessages) {
    messages.value = historyMessages.map((m, i) => ({
      id: m.id || Date.now() + i,
      role: m.role,
      content: m.content || '',
      toolCalls: (m.tool_calls || []).map(tc => reactive({
        name: tc.name,
        code: tc.code,
        result: tc.result || null,
        expanded: false,
      })),
      outputPath: m.output_path || null,
      error: m.error || null,
    }))
  }

  return { messages, streaming, status, send, stop, clearMessages, loadFromHistory }
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/composables/useChat.js
git commit -m "feat(ui): replace thinking boolean with status state machine"
```

---

### Task 8: 前端状态指示器 — ChatPanel.vue

**Files:**
- Modify: `frontend/src/components/ChatPanel.vue`

- [ ] **Step 1: 更新 script — 引入 status 和计时器**

替换 `ChatPanel.vue` 的 `<script setup>` 部分：

```javascript
import { ref, watch, nextTick, computed, onUnmounted } from 'vue'
import { FileSpreadsheet } from 'lucide-vue-next'
import { useChat } from '../composables/useChat'
import { useFiles } from '../composables/useFiles'
import { useConversations } from '../composables/useConversations'
import MessageBubble from './MessageBubble.vue'
import ChatInput from './ChatInput.vue'

const { messages, streaming, status, send } = useChat()
const { files } = useFiles()
const { currentConvId, create } = useConversations()
const scrollContainer = ref(null)
const userScrolledUp = ref(false)

// 计时器
const elapsed = ref(0)
let timerInterval = null
let timerStart = 0

watch(status, (val) => {
  if (val) {
    timerStart = Date.now()
    elapsed.value = 0
    if (!timerInterval) {
      timerInterval = setInterval(() => {
        elapsed.value = Math.floor((Date.now() - timerStart) / 1000)
      }, 1000)
    }
  } else {
    if (timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
    elapsed.value = 0
  }
})

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
})

const statusLabel = computed(() => {
  switch (status.value) {
    case 'thinking': return '分析中'
    case 'running': return '执行代码中'
    case 'verifying': return '验证结果中'
    case 'reporting': return '生成报告中'
    default: return ''
  }
})

async function handleSend(text, imageIds = []) {
  const fileIds = files.value.map(f => f.file_id)
  let convId = currentConvId.value
  if (!convId) {
    convId = await create()
  }
  send(text, fileIds, convId, imageIds)
}

function handleScroll() {
  const el = scrollContainer.value
  if (!el) return
  const threshold = 100
  userScrolledUp.value = el.scrollHeight - el.scrollTop - el.clientHeight > threshold
}

// 自动滚动到底部
watch(
  () => {
    const last = messages.value[messages.value.length - 1]
    return last?.content?.length || last?.toolCalls?.length || messages.value.length
  },
  async () => {
    if (userScrolledUp.value) return
    await nextTick()
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  }
)
```

- [ ] **Step 2: 更新 template — 多状态指示器**

替换 `ChatPanel.vue` 的 `<template>` 中思考指示器部分（`<!-- 思考指示器 -->` 注释开始的 `<div v-if="thinking" ...>` 块）为：

```html
        <!-- 状态指示器 -->
        <div v-if="status" class="flex items-center gap-2 text-[#999] text-sm mb-6 pl-0.5">
          <div class="flex gap-1" v-if="status === 'thinking'">
            <span class="w-1.5 h-1.5 bg-[#999] rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-1.5 h-1.5 bg-[#999] rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 bg-[#999] rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>
          <svg v-else class="w-4 h-4 animate-spin text-[#999]" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25" />
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          <span class="text-xs">{{ statusLabel }}</span>
          <span v-if="elapsed > 0" class="text-xs text-[#bbb]">{{ elapsed }}s</span>
        </div>
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/ChatPanel.vue
git commit -m "feat(ui): rich status indicator with phase labels and timer"
```

---

### Task 9: 构建部署验证

**Files:** 无新改动，验证所有 Task 的集成效果

- [ ] **Step 1: 前端构建验证**

```bash
cd /Users/lin/Desktop/Excel/frontend && npx vite build
```

预期：构建成功，无错误

- [ ] **Step 2: Docker 构建部署**

```bash
cd /Users/lin/Desktop/Excel && docker compose up -d --build
```

预期：容器正常启动

- [ ] **Step 3: 功能验证清单**

在浏览器中测试以下场景：

1. **无文件聊天** — 不上传文件直接发消息，应正常对话
2. **正常 Excel 处理** — 上传文件，发处理需求：
   - 状态指示器应依次显示：分析中 → 执行代码中(Ns) → 验证结果中 → 生成报告中
   - execute 成功后应立即出现下载按钮
   - 最后应输出自然语言变更报告（改了什么、怎么改、风险）
3. **LLM 交互质量** — 观察 LLM 是否：
   - 调工具前用文字说明意图
   - 没有重复执行相同的 query
4. **LoopGuard 验证** — 查看 Docker 日志确认 turn 计数正常：
   ```bash
   docker compose logs --tail=50
   ```

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "chore: build artifacts for agent optimization release"
```

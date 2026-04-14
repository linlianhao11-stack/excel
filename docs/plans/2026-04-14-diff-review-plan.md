# 实施计划：Excel 变更审查系统

> 设计文档：`2026-04-14-diff-review-design.md`
> 预计 6 个阶段，每阶段完成后做 review

---

## 阶段 1：工具拆分 + 格式保护（后端核心）

### 1.1 sandbox.py — 安全检查增强

- `check_code_safety()` 新增参数 `mode: str = "modify" | "create" | None`
- modify 模式新增 AST 拦截规则：
  - 拦截 `to_excel`/`to_csv`/`to_parquet` — 检测 `ast.Call` 中 `ast.Attribute.attr`
  - 拦截 `ExcelWriter` — 检测 `ast.Call` 中 `ast.Attribute.attr`
  - create 模式和 query（mode=None）不拦截
- `BLOCKED_ATTRS` 新增 `__getattribute__`，防止绕过拦截
- `_execute_code_sync()` 新增 `pre_copy_from: str | None` 参数：
  - 非 None 时，执行代码前先 `shutil.copy2(pre_copy_from, output_path)`
- INPUT 路径保护：modify 模式下，`_build_header` 中 INPUT 变量指向临时只读副本路径（通过 shutil.copy 到临时位置），防止 LLM 代码覆写原始文件

### 1.2 agent.py — 工具定义拆分

- 删除 `execute` 工具定义
- 新增 `modify` 工具定义：
  ```json
  {
    "name": "modify",
    "description": "修改现有 Excel 文件。系统已自动复制原文件到 OUTPUT_PATH，你只需要用 openpyxl 修改需要改的单元格。禁止使用 pandas 写文件。",
    "parameters": {
      "code": { "type": "string", "description": "要执行的 Python 代码" },
      "source": { "type": "string", "description": "要修改的文件变量名，默认 INPUT_PATH_1", "default": "INPUT_PATH_1" }
    }
  }
  ```
- 新增 `create` 工具定义：
  ```json
  {
    "name": "create",
    "description": "生成全新的 Excel 文件到 OUTPUT_PATH。可以使用 pandas 或 openpyxl。用于汇总、合并、生成新报表等场景。",
    "parameters": {
      "code": { "type": "string", "description": "要执行的 Python 代码" }
    }
  }
  ```
- `SYSTEM_PROMPT` 更新：
  - 说明三个工具的区别和使用场景
  - 强化规则：读取并修改现有文件必须用 modify，create 只用于从零生成新文件
  - 删除旧的"修改现有文件时用 openpyxl"的建议（现在系统强制了）

### 1.3 agent.py — 函数签名改造

- `run_agent()` 新签名：
  ```python
  async def run_agent(
      user_message: str = None,
      files: list = None,
      images: list = None,
      operation_history: list[str] = None,
      resume_messages: list[dict] = None,
  ):
  ```
- `resume_messages` 不为 None 时：
  - 跳过 system/user 构建，直接使用传入的 messages
  - LoopGuard 和 ErrorTracker 重置
  - 直接进入 while 循环
- `resume_messages` 为 None 时：
  - 正常构建 messages（含 operation_history 注入）

### 1.4 agent.py — 执行流程改造

- 工具调用分支：
  - `name == "modify"` → 从 args 取 source 参数 → `execute_code(code, file_paths, mode="modify", pre_copy_from=file_paths[source])`
  - `name == "create"` → `execute_code(code, file_paths, mode="create")`
- modify 成功后：
  - yield `{"type": "tool_result", ...}`
  - yield `{"type": "phase", "name": "verifying"}`
  - 调用 `compute_diff(input_path, output_path)`（阶段 2 实现，此阶段先占位）
  - yield `{"type": "diff_review", "diff": diff_data, "output_path": output_path, "input_path": input_path, "messages": messages}`
  - yield `{"type": "done", "output_path": None}` ← 不带 output_path，等审批
  - return
- create 成功后：
  - 调用 `compute_create_summary(output_path)`（阶段 2 实现，此阶段先占位）
  - yield `{"type": "create_summary", "summary": summary_data}`
  - yield `{"type": "output_ready", "output_path": output_path}`
  - yield `{"type": "done", "output_path": output_path}`
  - return

### 1.5 删除旧代码

- 删除 `build_verification_code()` 函数
- 删除 `_generate_report()` 函数
- 删除 `REPORT_PROMPT` 常量
- 更新 `_generate_interrupted_summary()`：适配 modify/create 场景
- 更新 `classify_error()` / `ErrorTracker`：确认适配新工具名

### 交接标记
- [ ] sandbox.py 安全检查增强完成（含 mode 参数、__getattribute__、INPUT 保护）
- [ ] agent.py 工具定义拆分完成
- [ ] agent.py run_agent 签名改造完成（resume_messages）
- [ ] agent.py 执行流程 modify/create 分支完成
- [ ] 旧代码删除完成
- [ ] 手动测试：modify 模式下 `to_excel` 被拦截
- [ ] 手动测试：create 模式下 `to_excel` 正常执行
- [ ] 手动测试：modify 模式预复制后格式保留
- [ ] 手动测试：modify 模式下 LLM 无法覆写 INPUT 文件

---

## 阶段 2：Diff 计算引擎（后端核心）

### 2.1 excel.py — compute_diff() 函数

新增函数 `compute_diff(input_path: str, output_path: str) -> dict`：

**读取方式：用 openpyxl 逐单元格读取**（不用 pandas），避免合并单元格/公式产生假阳性。

**行对齐算法：**
1. 取第一列作为匹配键
2. 如果第一列有重复值，退回索引位置对齐并在结果中标注
3. 用匹配键将输入行和输出行配对
4. 未配对的输入行 = deleted，未配对的输出行 = added
5. 已配对的行做逐单元格对比 = modified / unchanged

**行标识生成：**
- 取第一列的值作为 `row_label`
- 拼成人话：`产品「螺丝M6」(第5行)`

**完整性校验：**
- 未修改行 hash：对未变更行的所有单元格值做 hash，输入输出对比
- 数值列 sum：**用 pandas** 对所有数值列做 sum 对比
- sum 差异归因：分别对 modified/added/deleted 行计算各列 sum 差额，用模板生成 reason 字符串（如"修改行贡献 +100，新增行贡献 +195"）
- 列类型校验：对比每列 dtype

**超长改动处理：** 超过 50 条 changes 时，只返回前 50 条明细 + `"truncated": true` + `"total_changes": N`

**返回结构：** 见设计文档第四节

### 2.2 excel.py — compute_create_summary() 函数

新增函数 `compute_create_summary(output_path: str) -> dict`：

- 用 pandas 读取输出文件每个 sheet
- 返回：sheet 名、行数、列数、列名、前 5 行预览

### 2.3 excel.py — generate_operation_summary() 函数

新增函数 `generate_operation_summary(user_message: str, diff: dict) -> str`：

- 模板拼接，不依赖 LLM：
  ```python
  parts = [user_message[:50]]
  s = diff["summary"]
  if s["modified"]: parts.append(f"改了{s['modified']}个格子")
  if s["added"]: parts.append(f"新增{s['added']}行")
  if s["deleted"]: parts.append(f"删除{s['deleted']}行")
  return "（".join(parts) + "）"
  ```
- 示例输出：`"所有单价加10%（改了18个格子）"`

### 2.4 agent.py — 集成 diff 计算

替换阶段 1 中的占位逻辑：
- modify 成功后调用 `compute_diff(input_path, output_path)`
- 如果 `unchanged_rows_ok == false`，在 diff_review 事件中标记为异常
- create 成功后调用 `compute_create_summary(output_path)`

### 交接标记
- [ ] compute_diff() 实现完成（openpyxl 读取 + 行匹配对齐）
- [ ] compute_create_summary() 实现完成
- [ ] generate_operation_summary() 实现完成
- [ ] agent.py 集成 diff 计算
- [ ] 单元测试：准备测试 Excel 文件，验证 diff 计算准确性
- [ ] 边界测试：空文件、单行文件、多 sheet 文件
- [ ] 边界测试：合并单元格文件、含公式文件
- [ ] 边界测试：插入行/删除行后行对齐正确

---

## 阶段 3：审批 API + 上下文管理（后端）

### 3.1 新增 api/diff.py

**状态管理（内存字典）：**

```python
# 待审批的 diff
pending_diffs: dict[str, dict] = {}
# key: conversation_id
# value: {
#   "messages": [...],       # 完整 agent messages 数组
#   "diff": {...},           # diff 数据
#   "output_path": "...",    # 输出文件路径
#   "input_path": "...",     # 输入文件路径
#   "user_message": "...",   # 原始用户消息
#   "file_paths": {...},     # 文件路径映射
#   "retry_count": 0,        # 重试次数
# }

# 对话级状态
conversation_state: dict[str, dict] = {}
# key: conversation_id
# value: {
#   "operation_history": ["操作1摘要", "操作2摘要"],
#   "current_file": { "file_id": "...", "path": "...", "profile": {...} },
# }
```

**端点：**

`POST /api/diff/approve`
```json
请求：{ "conversation_id": "xxx" }
响应：{ "output_path": "/data/work/result_xxx.xlsx" }
```
1. 从 pending_diffs 取出记录
2. 调用 `generate_operation_summary()` 生成操作摘要
3. 更新 conversation_state：追加操作摘要 + current_file 指向 output
4. 对新的 current_file 重新 `profile_excel()` 更新 profile
5. 返回 output_path
6. 清理 pending_diffs 条目

`POST /api/diff/reject`
```json
请求：{
  "conversation_id": "xxx",
  "reason_type": "too_many | too_few | wrong | other",
  "reason_text": "第5行不应该改"
}
响应：StreamingResponse（SSE 流）
```
1. 检查 retry_count < 3，否则返回 JSON 错误
2. 从 pending_diffs 取出完整 messages 数组
3. 拼接反馈：`messages.append({"role": "user", "content": f"用户驳回了修改。原因：{reason_type} — {reason_text}。请重新修改。"})`
4. retry_count += 1
5. 调用 `run_agent(resume_messages=messages)`
6. 返回 `StreamingResponse(event_stream(), media_type="text/event-stream")`
7. event_stream 中拦截新的 diff_review 事件，更新 pending_diffs

### 3.2 chat.py 适配

- `event_stream()` 中拦截 `diff_review` 事件：
  - 提取 messages、output_path、input_path 存入 `pending_diffs[conv_id]`
  - 推给前端的 diff_review 事件**不包含 messages**（太大），只包含 diff 数据
- 处理 `create_summary` 事件：正常推给前端
- 用户发新消息时，从 `conversation_state` 取 current_file 和 operation_history
- 注册路由 `diff.router`

### 交接标记
- [ ] api/diff.py approve 端点完成（含操作摘要生成 + 文件状态更新）
- [ ] api/diff.py reject 端点完成（复用 messages + SSE 流返回）
- [ ] conversation_state 管理逻辑完成
- [ ] pending_diffs 拦截逻辑完成（chat.py event_stream）
- [ ] 重试次数限制 + 超限错误响应完成
- [ ] chat.py 适配新事件类型 + 状态读取
- [ ] 手动测试：approve 后 current_file 和 operation_history 更新正确
- [ ] 手动测试：reject 复用 messages，LLM 记得之前的操作
- [ ] 手动测试：连续 3 轮操作，每轮输入为上轮输出
- [ ] 手动测试：reject 3 次后第 4 次返回错误

---

## 阶段 4：前端审查面板

### 4.1 composables/useChat.js — 事件处理 + 状态管理

新增状态值：`reviewing`（区别于 streaming）

事件处理新增：
```javascript
case 'diff_review':
  status.value = 'reviewing'
  assistantMsg.diff = event.diff
  assistantMsg.conversationId = conversationId
  break
case 'create_summary':
  assistantMsg.createSummary = event.summary
  break
```

新增 `retryFromReject(conversationId, reasonType, reasonText)` 方法：
```javascript
function retryFromReject(conversationId, reasonType, reasonText) {
  // 创建新的 assistantMsg
  const assistantMsg = reactive({
    id: Date.now(),
    role: 'assistant',
    content: '',
    toolCalls: [],
    outputPath: null,
    error: null,
    diff: null,
  })
  messages.value.push(assistantMsg)
  
  streaming.value = true
  status.value = 'thinking'
  
  // 调用 reject API，消费返回的 SSE 流
  controller = rejectDiffStream(
    conversationId, reasonType, reasonText,
    (event) => { /* 同 send() 的事件回调 */ }
  )
}
```

### 4.2 components/DiffReview.vue — 审查面板

**Props：**
- `diff`: diff JSON 数据
- `conversationId`: 对话 ID
- `approved`: boolean，是否已审批

**面板结构（按设计文档第六节）：**
- 标题、一句话总结、安全提示条、改动清单、数值校验
- 超过 20 条改动时折叠显示
- 底栏按钮：「没问题，下载文件」/「不对，重新改」
- approved 状态下：灰色背景，显示「已确认」，按钮隐藏

**交互：**
- 点「没问题，下载文件」→ 调用 approveDiff → 拿到 output_path → 触发下载 → 设 approved=true
- 点「不对，重新改」→ 弹出 RejectModal
- 收到重试超限错误 → 在面板底部显示提示

### 4.3 components/RejectModal.vue — 驳回引导

**结构：**
- 四个预设选项（radio）：改多了 / 改少了 / 改错了 / 其他
- 其他选项展开文本输入框
- 取消 + 确认按钮

**交互：**
- 确认后调用 useChat().retryFromReject()
- Modal 关闭，等待新的 diff_review 事件

### 4.4 components/MessageBubble.vue — 集成

- 当消息包含 `diff` 数据时，渲染 `<DiffReview>` 组件
- 当消息包含 `createSummary` 时，渲染摘要卡片 + 下载按钮
- 无 diff 且无 createSummary 时，保持现有渲染逻辑
- outputPath 只在审批通过后显示下载按钮

### 4.5 api/index.js — 新增 API 调用

```javascript
export const approveDiff = (conversationId) =>
  api.post('/api/diff/approve', { conversation_id: conversationId })

export function rejectDiffStream(conversationId, reasonType, reasonText, onEvent) {
  // 类似 chatStream，用 fetch 消费 SSE 流
  const controller = new AbortController()
  fetch('/api/diff/reject', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ conversation_id: conversationId, reason_type: reasonType, reason_text: reasonText }),
    signal: controller.signal,
  }).then(resp => {
    // 消费 SSE 流，调用 onEvent 回调
  })
  return controller
}
```

### 4.6 ChatPanel.vue — 状态指示

`statusLabel` computed 新增：
- `'reviewing'` → "等待确认"（但 reviewing 状态下不显示 spinner，只显示 DiffReview 面板）

### 交接标记
- [ ] useChat.js 新事件处理 + retryFromReject 完成
- [ ] DiffReview.vue 组件完成（含折叠、审批后状态）
- [ ] RejectModal.vue 组件完成
- [ ] MessageBubble.vue 集成完成
- [ ] api/index.js approveDiff + rejectDiffStream 完成
- [ ] ChatPanel.vue 状态适配
- [ ] 构建通过 `npm run build`
- [ ] 视觉验证：审查面板展示效果
- [ ] 交互验证：确认流程端到端
- [ ] 交互验证：驳回流程端到端（含新 assistantMsg 创建）
- [ ] 交互验证：驳回超限提示

---

## 阶段 5：上下文管理集成（后端 + 前端联调）

### 5.1 chat.py — 跨任务上下文组装

用户在同一对话发送新消息时：
```python
state = conversation_state.get(conv_id, {})

if state.get("current_file"):
    # 用最新文件替代原始上传
    current = state["current_file"]
    files = [current]
else:
    files = [uploaded_files[fid] for fid in req.file_ids]

operation_history = state.get("operation_history", [])

async for event in run_agent(req.message, files, images, operation_history):
    ...
```

### 5.2 agent.py — 历史摘要注入

构建 user message 时拼入操作历史：

```python
if operation_history:
    history_text = "历史操作：\n"
    for i, op in enumerate(operation_history, 1):
        history_text += f"{i}. {op}\n"
    user_text = f"已上传的文件信息：\n\n{context}\n\n{history_text}\n本次需求：{user_message}"
```

### 5.3 token 兜底

在 `run_agent()` 构建完 messages 后、发送 LLM 前做检查：

```python
estimated_tokens = len(json.dumps(messages, ensure_ascii=False)) // 2
if estimated_tokens > 500_000 and operation_history:
    operation_history = operation_history[-5:]
    # 用裁剪后的 history 重建 user message
```

### 交接标记
- [ ] chat.py 跨任务上下文组装完成
- [ ] agent.py 历史摘要注入完成
- [ ] token 兜底检查完成
- [ ] 手动测试：第 2 轮操作使用第 1 轮输出文件
- [ ] 手动测试：LLM 能看到历史操作摘要并正确理解
- [ ] 手动测试：连续 5 轮操作，上下文不膨胀

---

## 阶段 6：集成测试 + 清理

### 6.1 端到端测试

- 场景 1：上传 Excel → modify → diff 审查 → 确认下载 → 验证格式保留
- 场景 2：上传 Excel → modify → diff → 驳回（改错了）→ LLM 重试（复用上下文）→ 新 diff → 确认
- 场景 3：上传 Excel → create → 摘要展示 → 直接下载
- 场景 4：上传带格式的 Excel（合并单元格、颜色、公式）→ modify → 确认格式完整保留
- 场景 5：LLM 在 modify 中尝试 to_excel → 安全检查拦截 → LLM 重试用 openpyxl
- 场景 6：同一对话连续 3 轮 modify → 每轮输入为上轮输出 → LLM 看到历史摘要
- 场景 7：驳回 3 次 → 第 4 次返回错误提示 → 上下文正常

### 6.2 清理

确认以下旧代码已在阶段 1 删除：
- [ ] `build_verification_code()` 已删除
- [ ] `_generate_report()` 已删除
- [ ] `REPORT_PROMPT` 已删除
- [ ] `INTERRUPTED_PROMPT` 已更新
- [ ] `SYSTEM_PROMPT` 中 execute 相关描述已更新
- [ ] agent.py 中旧 execute 分支已删除

### 6.3 文档更新

- [ ] CLAUDE.md 更新（如有需要）
- [ ] CHANGELOG 记录版本变更

### 交接标记
- [ ] 7 个场景端到端测试通过
- [ ] 旧代码清理确认完成
- [ ] Docker 构建验证通过（`docker-compose build && docker-compose up`）

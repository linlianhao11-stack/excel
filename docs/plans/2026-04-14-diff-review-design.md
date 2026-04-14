# 设计文档：Excel 变更审查系统

> 日期：2026-04-14
> 目标：保证 Excel 处理结果 100% 准确，格式不丢失，用户完全知情

## 一、问题

当前系统 LLM 生成代码处理 Excel 后，用户直接下载结果文件。存在三个隐患：

1. **数据可能被改错** — LLM 代码有 bug，用户无从得知
2. **格式可能丢失** — LLM 用 pandas 写文件会丢掉样式/合并单元格/公式
3. **用户完全不知道改了什么** — 下载前没有任何审查环节

## 二、设计目标

- 格式保护在系统层面强制执行，不依赖 LLM 自觉
- 每一个被改动的单元格都要展示给用户
- 用户确认后才能下载，驳回可带原因自动重试
- 所有交互用大白话，面向不懂 Excel 的用户

## 三、工具拆分

### 现有工具
- `query` — 只读探索
- `execute` — 执行代码生成文件

### 改为
- `query` — 不变
- `modify` — 修改现有表（保格式）
- `create` — 生成新表（自由发挥）

### modify 工具机制

1. **系统预复制**：在 LLM 代码执行前，系统自动 `shutil.copy2(source_file, OUTPUT_PATH)`
2. **禁止 pandas 写文件**：AST 安全检查拦截 `to_excel`、`to_csv`、`ExcelWriter`、`to_parquet`
3. **LLM 只能用 openpyxl** 操作已复制的 OUTPUT_PATH 副本
4. **INPUT 路径保护**：`_build_header` 中 INPUT 变量指向只读临时副本，LLM 无法覆写原始文件
5. **结果**：原始格式（样式、合并单元格、列宽、公式）在系统层面不可能丢失

### modify 工具参数

```json
{
  "name": "modify",
  "parameters": {
    "code": "要执行的 Python 代码",
    "source": "要修改的文件变量名，默认 INPUT_PATH_1"
  }
}
```

LLM 通过 `source` 参数声明要修改哪个文件（多文件场景下可能是 `INPUT_PATH_2`），系统据此决定预复制哪个文件。

### create 工具机制

1. 不做预复制
2. pandas / openpyxl 都可以用
3. 生成全新文件，无格式保护需求

### LLM 选错工具的兜底

- 用 `modify` 但代码里 `to_excel` → AST 检查直接拦截，报错让 LLM 重试
- 用 `create` 但代码读取了 INPUT_PATH → SYSTEM_PROMPT 中强化规则：读取现有文件并修改必须用 modify，create 只用于从零生成

### AST 安全检查补充

- 将 `__getattribute__` 加入 `BLOCKED_ATTRS`，防止绕过 pandas 写文件拦截

## 四、Diff 计算

### 实现方式

后端新增正式 Python 函数 `compute_diff()`。确定性系统代码，**用 openpyxl 读取逐单元格对比**（不用 pandas，避免合并单元格/公式产生假阳性）。数值列 sum 校验单独用 pandas 处理。

### 行对齐算法

不使用纯索引位置对齐（插入/删除行会导致大量误报），而是：

1. 取第一列（或看起来像编号/ID 的列）作为匹配键
2. 用匹配键将输入行和输出行配对
3. 未配对的输入行 = deleted，未配对的输出行 = added
4. 已配对的行做逐单元格对比 = modified / unchanged

如果没有合适的匹配键（第一列有重复值），退回到索引位置对齐并在 diff 结果中标注。

### 对比内容

| 检查项 | 说明 |
|--------|------|
| 逐单元格对比 | 每个被修改的单元格：行号、列名、旧值、新值 |
| 未修改行 hash | 不在变更范围内的行，逐行 hash 确认没被误改 |
| 数值列 sum | 金额/数量等数值列的总和对比（用 pandas） |
| 列类型校验 | 确保列的数据类型没被意外改变 |
| 行数校验 | 新增/删除的行数统计 |

### 返回结构

```json
{
  "summary": {
    "modified": 3,
    "added": 2,
    "deleted": 1,
    "unchanged": 45
  },
  "integrity": {
    "unchanged_rows_ok": true,
    "type_changes": [],
    "sum_checks": [
      {
        "column": "金额",
        "before": 56840,
        "after": 57135,
        "diff": 295,
        "reason": "修改行贡献 +100，新增行贡献 +195"
      }
    ]
  },
  "changes": [
    {
      "type": "modified",
      "row": 5,
      "col_name": "单价",
      "row_label": "产品「螺丝M6」",
      "old": "128.00",
      "new": "138.00",
      "note": "金额也跟着变了：1,280 → 1,380"
    },
    {
      "type": "added",
      "row": 51,
      "data": {"编号": "P-0051", "名称": "螺丝M6", "数量": "500", "金额": "175.00"}
    },
    {
      "type": "deleted",
      "row": 23,
      "row_label": "产品「废品退回」",
      "data": {"编号": "P-0023", "名称": "废品退回", "数量": "1", "金额": "50.00"}
    }
  ]
}
```

### 超长改动清单处理

如果改动超过 50 条，diff 结果中只保留前 50 条明细 + 统计摘要（"还有 N 处改动"）。前端展示时默认折叠，显示"还有 X 条改动，点击展开"。

### modify vs create 的 diff 差异

- **modify**：完整 diff（逐单元格 + hash + sum），有原始文件可对比
- **create**：只展示输出文件摘要（行数、列名、前几行预览），无 diff，无审批门

## 五、事件流改造

### 现有事件流（execute 成功后）

```
execute 成功 → output_ready(下载按钮出现) → phase:verifying → phase:reporting → LLM写报告 → done
```

### 新事件流（modify 成功后）

```
modify 成功
  → phase:verifying
  → 系统计算 diff
  → diff_review(diff 数据推给前端)
  → done(不带 output_path) ← SSE 连接正常关闭，前端进入 reviewing 状态
  → chat.py 拦截 diff_review 事件，将 messages + diff + output_path 存入 pending_diffs

用户确认：
  → POST /api/diff/approve
  → 返回 JSON { output_path }
  → 前端显示下载按钮

用户驳回：
  → POST /api/diff/reject(带原因)
  → 从 pending_diffs 取出 messages，追加用户反馈
  → 重新调用 run_agent(resume_messages=messages)
  → 返回 StreamingResponse（SSE 流，和 chat 端点格式相同）
  → 前端创建新 assistantMsg 消费流
  → 新一轮 modify → diff_review → done → 等待用户操作
```

**关键设计点：**
- SSE 不"暂停"。推 `diff_review` 后正常推 `done`，连接正常关闭
- `pending_diffs` 暂存 messages 数组，reject 时取出复用
- reject 端点返回 `StreamingResponse`，和 `/api/chat` 格式相同
- `run_agent` 是重新调用（传入修改后的 messages），不是暂停/恢复 generator

### 新事件流（create 成功后）

```
create 成功 → phase:verifying → create_summary(摘要数据) → output_ready → done
```

create 不需要审批门，不走 LLM 报告流程。直接推摘要 + output_ready + done。

### 新增 SSE 事件类型

| 事件 | 数据 | 说明 |
|------|------|------|
| `diff_review` | diff JSON | 前端渲染审查面板 |
| `create_summary` | 摘要 JSON | 前端渲染新建文件摘要 |

### 新增 API 端点

| 端点 | 方法 | 响应类型 | 说明 |
|------|------|----------|------|
| `/api/diff/approve` | POST | JSON | 用户确认变更，返回 output_path |
| `/api/diff/reject` | POST | SSE 流 | 用户驳回，触发 LLM 重试 |

## 六、前端审查面板

### 面板语气

像一个认真负责的助手在汇报，不是系统在展示报表。全部大白话。

### 面板结构

```
标题：帮你改好了，确认一下？

一句话总结：改了 3 个格子，加了 2 行新数据，删了 1 行。其余 45 行没动过。

安全提示（绿色条）：其他数据都检查过了，没有被误改 ✓

改动清单（每条一个卡片）：
  [改] 产品「螺丝M6」(第5行) 的单价从 128 改成了 138
       金额也跟着变了：1,280 → 1,380
  [改] 第 12 行「备注」从 待确认 改成了 已审核
  [加] 新加了 2 行数据（第 51、52 行）
       螺丝M6 500个 ¥175 / 垫片D10 1000个 ¥120
  [删] 删掉了「废品退回」那行（第23行）

底栏：
  [没问题，下载文件]  [不对，重新改]
```

### 每条变更的定位方式

不说"第5行B列"，用这行的**关键信息**定位：
- 自动取第一列或名称/编号列作为标识
- 拼成：产品「螺丝M6」(第5行) 的「单价」

### 数值变化的解读

不只报数字，解释差异来源：
- "金额总数多了 295 块：修改行贡献 +100，新增行贡献 +195"

### 安全提示的两种状态

- ✅ 通过：「其他数据都检查过了，没有被误改」
- ❌ 异常：「注意：有 2 行数据可能被误改了，请仔细检查」（红色警告）

### 超长改动列表

超过 20 条改动时默认折叠，显示"还有 X 条改动，点击展开"。

### 审批后状态

审批通过后，DiffReview 组件变为已确认状态（灰色背景，显示「已确认」），下载按钮出现在下方。

## 七、驳回闭环

### 驳回引导

用户点"不对，重新改"后弹出引导：

```
哪里不对？（选一个或自己写）

○ 改多了 — 有些不该改的被改了
○ 改少了 — 还有些该改的没改到
○ 改错了 — 改的方向/数值不对
○ 其他：[________________]
```

### 驳回数据流时序

```
1. 用户点"不对，重新改" → 弹出 RejectModal
2. 用户选原因/填文字 → 点确认
3. 前端调用 POST /api/diff/reject { conversation_id, reason_type, reason_text }
4. 后端从 pending_diffs[conv_id] 取出完整 messages 数组
5. messages.append({"role": "user", "content": "用户驳回了修改。原因：{reason}。请重新修改。"})
6. 重新调用 run_agent(resume_messages=messages)，LoopGuard/ErrorTracker 重置
7. 返回 StreamingResponse（SSE 流）
8. 前端创建新 assistantMsg，调用 retryFromReject() 消费 SSE 流
9. LLM 基于完整上下文修正 → 新 modify → 新 diff_review → done
10. 前端展示新的 DiffReview 面板
```

### 重试次数限制

最多重试 3 次（pending_diffs 中记录 retry_count）。超过后 reject 端点返回 JSON 错误 `{"error": "已达最大重试次数，请换个方式描述需求"}`，前端在 DiffReview 组件中展示提示。

### 驳回时上下文增量

每次驳回在 messages 末尾追加一条用户反馈（~100 token）+ LLM 新一轮处理（~2000-5000 token）。3 次驳回增加约 6K-15K token，对 1M 窗口完全无压力。

## 八、上下文管理

### 设计原则

Qwen 3.6 支持 1M token（约 150 万中文字符），窗口足够大。不做复杂的压缩引擎（那是通用聊天机器人才需要的），靠"聪明地组装上下文"解决问题。

### run_agent 函数签名改造

```python
async def run_agent(
    user_message: str = None,
    files: list = None,
    images: list = None,
    operation_history: list[str] = None,
    resume_messages: list[dict] = None,   # 驳回重试时传入
):
    if resume_messages:
        # 跳过 system/user 构建，直接使用传入的 messages
        messages = resume_messages
    else:
        # 正常构建 messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_content(...)},
        ]
    
    guard = LoopGuard()   # 每次调用都重置
    errors = ErrorTracker()
    ...
```

### 场景 1：驳回重试（同一任务内）

reject 端点从 pending_diffs 取出 messages → append 反馈 → 重新调用 run_agent(resume_messages=messages)。LLM 看到完整的探索过程和上次的修改结果，直接修正。

### 场景 2：同一对话连续操作（跨任务）

每次任务完成（approve）后：
1. 生成操作摘要：`"{user_message}（改了{n}个格子）"` — 模板拼接，不靠 LLM
2. 更新当前文件：output 变为下一轮的 input
3. 重新 profile 最新文件

下次用户发消息时，构建 user message：

```
已上传的文件信息：
（最新文件的 profile）

历史操作：
1. 所有单价加了10%（改了18个格子）
2. 备注列全部清空（清了45个格子）

本次需求：删掉金额为0的行
```

### 场景 3：兜底保护

```python
estimated_tokens = len(json.dumps(messages, ensure_ascii=False)) // 2  # 粗略上限估算，偏保守
if estimated_tokens > 500_000:
    operation_history = operation_history[-5:]  # 裁剪到最近 5 条
```

### 数据流：文件状态流转

```
用户上传 file_A.xlsx
  → 第1轮：modify → 输出 result_1.xlsx → 用户确认
  → 第2轮：modify → 输入变为 result_1.xlsx → 输出 result_2.xlsx → 用户确认
  → 第3轮：modify → 输入变为 result_2.xlsx → 输出 result_3.xlsx → 用户确认
```

### 状态持久化

**短期方案（本次实现）：** `conversation_state` 和 `pending_diffs` 存储在内存字典中。进程重启后状态丢失，行为与现有 `uploaded_files` 一致——用户需要重新上传文件开始新对话。

**后续改进：** 将 `operation_history` 和 `current_file` 持久化到 SQLite（扩展 conversations 表），实现进程重启后对话级状态恢复。

### 不做的事

- **不做时间过期**：主流产品（Claude、ChatGPT、Gemini）都不做时间过期
- **不做分级压缩引擎**：我们是聚焦工具，不需要
- **不做跨对话记忆**：每个对话围绕一组文件，新文件开新对话

## 九、文件改动清单

### 后端

| 文件 | 改动 |
|------|------|
| `services/excel.py` | 新增 `compute_diff()`（openpyxl 逐单元格对比）、`compute_create_summary()`、`generate_operation_summary()` |
| `services/agent.py` | 拆 execute 为 modify/create；TOOLS 定义更新；SYSTEM_PROMPT 更新；新增 `resume_messages` 参数；删除 `build_verification_code()`、`_generate_report()`、`REPORT_PROMPT`、`INTERRUPTED_PROMPT`；更新 LoopGuard 中断处理 |
| `services/sandbox.py` | `check_code_safety()` 新增 mode 参数和 modify 模式拦截；`__getattribute__` 加入 BLOCKED_ATTRS；`_execute_code_sync` 支持预复制模式；INPUT 路径保护 |
| `api/chat.py` | 拦截 diff_review 事件存入 pending_diffs；操作摘要管理；文件状态流转 |
| `api/diff.py` | 新文件：approve/reject 端点；pending_diffs + conversation_state 管理；重试机制 |

### 前端

| 文件 | 改动 |
|------|------|
| `composables/useChat.js` | 处理 `diff_review`/`create_summary` 事件；新增 `retryFromReject()` 方法；新增 `reviewing` 状态 |
| `components/DiffReview.vue` | 新组件：审查面板（大白话版），支持折叠长列表 |
| `components/RejectModal.vue` | 新组件：驳回原因引导弹窗 |
| `components/MessageBubble.vue` | 集成 DiffReview；下载按钮改为审批后才显示；create_summary 展示 |
| `api/index.js` | 新增 `approveDiff()`、`rejectDiff()` API 调用 |

## 十、不做的事

- 不做 LLM 意图声明 + 规则验证（复杂度高，留到后续）
- 不做双重执行对比（成本翻倍，当前层级够用）
- 不改 query 工具（只读操作无需审查）
- 不改前端预览弹窗（ExcelPreview 保持现状）
- 不做 conversation_state 持久化到 SQLite（留到后续）

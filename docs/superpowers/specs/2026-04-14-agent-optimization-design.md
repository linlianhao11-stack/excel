# Excel Agent 优化设计方案

## 背景

当前 Agent 存在以下问题：
1. LLM 无限循环 — execute 成功后继续调工具，不停手
2. query 探索过多 — 连续 7-8 次重复探索才开始执行
3. 错误重试粗糙 — 只有全局计数器，不区分错误类型
4. 执行完不报告 — 用户不知道改了什么、怎么改的、有什么风险
5. 准确率无保障 — 零验证，改错了用户不知道
6. UI 状态断层 — 代码执行期间没有加载指示，"思考中"有时无
7. 交互体验差 — LLM 默默跑工具不解释，模糊需求直接猜着做

## 设计总览

采用方案 B（提示词 + LoopGuard 代码护栏），分三层优化：

```
┌─────────────────────────────────────────────┐
│  系统提示词（引导层）                          │
│  - 分阶段工作流 + 交互纪律 + 报告要求          │
├─────────────────────────────────────────────┤
│  Agent 代码护栏（保障层）                      │
│  - LoopGuard + 强制报告模式 + 自动验证 + 错误分类│
├─────────────────────────────────────────────┤
│  前端 UI（展示层）                            │
│  - 状态机替代布尔值 + 阶段事件 + 计时器         │
└─────────────────────────────────────────────┘
```

---

## 一、系统提示词重写

### 1.1 分阶段工作流

将当前松散的提示词重构为明确的阶段指引：

**探索阶段**：用 query 理解数据，要求每次 query 前用文字说明意图（"我先看一下A列的空值分布"），query 后解读结果。禁止重复执行相同的 query。

**执行阶段**：确认理解后用 execute 生成结果。涉及批量修改/删除时，先说明方案让用户知晓。execute 前只动需要改的部分，不整列覆写。

**报告阶段**：execute 成功后，用自然语言段落说明：做了哪些修改、具体怎么改的、为什么这么改、可能存在的风险或注意事项。

### 1.2 交互纪律

- **边做边说**：每次调工具前用文字说明意图，调完后解读结果
- **大操作前说明**：批量修改/删除/改公式前，先描述方案
- **模糊需求主动澄清**：任务不明确时先问清楚再动手
- **禁止重复调用**：不得用完全相同的参数重复调用同一工具
- **execute 成功后不再调工具**：直接进入报告阶段

### 1.3 报告要求

execute 成功后，以自然语言段落输出变更报告，覆盖以下内容（不要求固定模板，LLM 自由组织语言）：
- 做了什么修改
- 具体怎么改的（涉及哪些 sheet、列、行范围）
- 为什么这么改
- 可能存在的风险、边界情况、未处理的异常数据

---

## 二、Agent 代码护栏

### 2.1 LoopGuard

在 agent.py 中新增 LoopGuard 类，三重检测：

```python
class LoopGuard:
    max_turns = 25              # 总轮数硬上限
    max_same_tool = 3           # 相同代码签名最多重复 3 次
    max_consecutive_query = 8   # 连续 query 不超过 8 次

    # 方法：
    # on_turn() → 检查总轮数
    # on_tool_call(name, code) → 检查重复签名、连续 query 计数
    # 返回: None（继续）或 str（终止原因）
```

触发 LoopGuard 时的行为：不是直接报错退出，而是**给 LLM 最后一次机会生成中断总结**（参考 smolagents 的 `provide_final_answer` 模式）。使用独立的 `INTERRUPTED_PROMPT`（区别于成功时的 `REPORT_PROMPT`），要求 LLM 如实总结已完成的进度和未完成的部分，不编造结果。

### 2.2 Execute 后强制报告模式

execute 成功后，代码层面不再将控制权交还给普通 agent 循环，而是：

1. 运行自动验证（见 2.3）
2. 构建一条特殊的 user 消息，包含验证结果，要求 LLM 生成变更报告
3. 调用 LLM **不传 tools 参数**（纯文本回复，无法再调工具）
4. 流式输出报告内容
5. 结束

这从代码层面杜绝了"execute 成功后继续调工具"的可能。

### 2.3 自动验证

execute 成功后，在报告阶段之前，自动执行一段验证代码：

对比输入文件和输出文件（自动区分 CSV 和 Excel 格式）：
- 按 (输入文件名, sheet 名) 维度逐个对比，避免多文件同名 sheet 混淆
- 每个 sheet 的行数、列数变化
- 逐列空值变化（哪些列的空值增减了）
- 输入前 3 行 vs 输出前 3 行的 before/after 抽样对比
- 输出中新增的 sheet 单独列出

验证结果作为上下文传给 LLM，让报告更准确。同时，如果发现严重异常（行数减少超过 50%、大量新空值），在报告中自动标注警告。

验证代码在沙箱中执行，复用现有的 `execute_query` 机制。

### 2.4 错误分类重试

替换当前的全局 `retry_count`，按错误类型分别处理：

| 错误类型 | 识别方式 | 处理策略 |
|---------|---------|---------|
| 语法错误 / NameError / TypeError | stderr 关键词匹配 | 回传错误给 LLM 修代码，最多重试 3 次 |
| FileNotFoundError / 路径错误 | stderr 包含 FileNotFound | 回传错误 + 提示检查路径变量 |
| 超时 (>30s) | subprocess timeout | 直接终止，告知用户数据量可能过大 |
| 内存不足 / MemoryError | stderr 关键词 | 直接终止，建议分批处理 |

每种错误类型独立计数，不互相消耗重试次数。

---

## 三、前端 UI 优化

### 3.1 状态机替代布尔值

将 `useChat.js` 中的 `thinking: ref(false)` 替换为 `status: ref(null)`：

```
status 取值：
  'thinking'   → 等待 LLM 响应（发送后、tool_result 后）
  'running'    → 沙箱执行代码中（tool_call 后、tool_result 前）
  'verifying'  → 自动验证中（后端推送 phase 事件）
  'reporting'  → 生成变更报告中（后端推送 phase 事件）
  null         → 空闲 / 文字流式输出中
```

事件映射：
- `send()` → `status = 'thinking'`
- `text` 事件 → `status = null`
- `tool_call` 事件 → `status = 'running'`
- `tool_result` 事件 → `status = 'thinking'`
- `phase` 事件 → `status = event.name`（'verifying' / 'reporting'）
- `done` / `error` → `status = null`

### 3.2 后端推送阶段事件

agent.py 在关键节点推送 `phase` 事件：

```python
yield {"type": "phase", "name": "verifying"}   # 进入验证阶段
yield {"type": "phase", "name": "reporting"}    # 进入报告阶段
```

### 3.3 状态指示器 UI

ChatPanel.vue 中用 `status` 驱动显示：

```
status='thinking'   → ● ● ● 分析中...
status='running'    → ⟳ 执行代码中... 8s
status='verifying'  → ⟳ 验证结果中...
status='reporting'  → ⟳ 生成报告中...
```

加入计时器：`status` 变为非 null 时记录起始时间，每秒更新显示。`status` 变为 null 时清除。

---

## 四、文件改动范围

| 文件 | 改动内容 |
|------|---------|
| `backend/app/services/agent.py` | 重写核心：LoopGuard、强制报告模式、自动验证、阶段事件推送、错误分类 |
| `backend/app/services/agent.py` | SYSTEM_PROMPT 完全重写 |
| `backend/app/api/chat.py` | 处理新事件类型 `phase` |
| `frontend/src/composables/useChat.js` | `thinking` → `status` 状态机，处理 `phase` 事件 |
| `frontend/src/components/ChatPanel.vue` | 状态指示器升级：多状态文案 + 计时器 |

不涉及的文件：MessageBubble.vue、ChatInput.vue、Sidebar.vue、数据库、API 路由等均不需改动。

---

## 五、不做的事情

- 不做多 agent 架构（过度设计）
- 不做硬性报告模板（用户选了自然语言段落）
- 不做交互式确认流程（增加用户操作负担，靠报告里的风险提示即可）
- 不改 LLM provider / 模型选择逻辑
- 不改文件上传、下载、预览等无关模块

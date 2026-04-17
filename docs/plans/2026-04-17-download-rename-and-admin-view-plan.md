# 下载重命名 + 管理员全局对话管理 实施计划

**Goal**：两个功能——下载文件用有意义的名字 + 管理员在设置页查看/管理所有用户的对话。

**Architecture**：
- 下载：磁盘名不变，存 `output_display_name` 到 messages，下载端点支持 display_name 参数
- 管理员视图：扩展 conversations API 支持 scope + 管理员绕过检查，设置页新增表格组件

**Tech Stack**：FastAPI + SQLite / Vue 3 / axios

**设计文档**：`docs/plans/2026-04-17-download-rename-and-admin-view-design.md`

**验证**：后端 curl + 前端 `npm run build`

---

## 任务索引

### Chunk A：下载重命名
- Task 1: `messages` 表加 `output_display_name` 迁移
- Task 2: `conversations.py` 的 `save_message` / `update_last_assistant_output` / `get_messages` 扩展字段
- Task 3: `agent.py` 计算并传入 display_name
- Task 4: `download.py` 支持 display_name 参数
- Task 5: 前端 API + useChat 读取 + MessageBubble 透传

### Chunk B：管理员全局对话管理
- Task 6: `conversations.py` list / get_messages / delete 加 admin scope + JOIN users
- Task 7: `api/index.js` 的 `listConversations` 支持 `scope` 参数
- Task 8: 新建 `ConversationPreviewModal.vue`
- Task 9: 新建 `AdminConversationsPanel.vue`（表格 + 预览 + 删除）
- Task 10: `SettingsPage.vue` 接入

### Chunk C：部署
- Task 11: scp + docker rebuild + 生产验证

---

## Task 1: `messages` 表加 `output_display_name`

**Files**: `backend/app/database.py`

**Step 1**：修改 SCHEMA（`CREATE TABLE IF NOT EXISTS messages`）加字段：

```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT,
    tool_calls TEXT,
    output_path TEXT,
    output_display_name TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Step 2**：在 `init_db()` 里加兼容迁移（在已有 is_active 迁移之后）：

```python
cols = {row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
if "output_display_name" not in cols:
    conn.execute("ALTER TABLE messages ADD COLUMN output_display_name TEXT")
    conn.commit()
```

**Step 3**：本地验证

```bash
cd ~/Desktop/Excel/backend
mkdir -p /tmp/excel_mig2 && rm -f /tmp/excel_mig2/excel_agent.db
DB_DIR=/tmp/excel_mig2 python -c "from app.database import init_db; init_db()"
sqlite3 /tmp/excel_mig2/excel_agent.db ".schema messages"
```

Expected：`messages` 表含 `output_display_name TEXT`

**Step 4**：Commit
```bash
git add backend/app/database.py
git commit -m "feat(download): messages 表加 output_display_name 字段"
```

---

## Task 2: `conversations.py` 扩展字段

**Files**: `backend/app/api/conversations.py`

**Step 1**：修改 `save_message` 签名，增加 `output_display_name` 参数：

```python
def save_message(
    conv_id: str,
    role: str,
    content: str | None = None,
    tool_calls: list | None = None,
    output_path: str | None = None,
    output_display_name: str | None = None,
    error: str | None = None,
) -> None:
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, tool_calls, output_path, output_display_name, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            conv_id,
            role,
            content,
            json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            output_path,
            output_display_name,
            error,
        ),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conv_id,),
    )
    conn.commit()
    conn.close()
```

**Step 2**：修改 `update_last_assistant_output` 签名支持同步更新 display_name：

```python
def update_last_assistant_output(
    conv_id: str, output_path: str, output_display_name: str | None = None
) -> None:
    conn = get_db()
    conn.execute(
        """UPDATE messages SET output_path = ?, output_display_name = ?
           WHERE id = (
               SELECT id FROM messages
               WHERE conversation_id = ? AND role = 'assistant'
               ORDER BY id DESC LIMIT 1
           )""",
        (output_path, output_display_name, conv_id),
    )
    conn.commit()
    conn.close()
```

**Step 3**：修改 `get_messages` SQL，返回 `output_display_name`：

```python
rows = conn.execute(
    "SELECT id, role, content, tool_calls, output_path, output_display_name, error, created_at "
    "FROM messages WHERE conversation_id = ? ORDER BY created_at",
    (conv_id,),
).fetchall()
```

**Step 4**：Commit

```bash
git add backend/app/api/conversations.py
git commit -m "feat(download): save_message/update_last_assistant_output 支持 display_name"
```

---

## Task 3: `agent.py` 计算并传入 display_name

**Files**: `backend/app/services/agent.py`

**Step 1**：加一个工具函数 `_compute_display_name`，放在文件合适位置（比如靠近 `_generate_interrupted_summary` 之前）：

```python
from datetime import datetime
from pathlib import Path

def _compute_display_name(
    mode: str,
    conversation_files: list[dict],
    source_var: str | None = None,
) -> str:
    """根据 modify/create 模式 + 输入文件计算下载显示名。

    modify: {原文件名无扩展}_已修改.xlsx
    create 有输入: {首个文件名无扩展}_汇总.xlsx
    create 无输入: 结果_YYYYMMDD_HHMMSS.xlsx
    """
    if mode == "modify" and source_var:
        # 根据 source_var (e.g. "INPUT_PATH_1") 定位到 conversation_files 的 index
        # source_var 格式为 INPUT_PATH_N，N 从 1 开始
        try:
            idx = int(source_var.rsplit("_", 1)[-1]) - 1
            if 0 <= idx < len(conversation_files):
                base = Path(conversation_files[idx]["filename"]).stem
                return f"{base}_已修改.xlsx"
        except (ValueError, IndexError, KeyError):
            pass
        # 降级：用第一个
        if conversation_files:
            base = Path(conversation_files[0]["filename"]).stem
            return f"{base}_已修改.xlsx"

    if mode == "create":
        if conversation_files:
            base = Path(conversation_files[0]["filename"]).stem
            return f"{base}_汇总.xlsx"

    # 无输入 或 异常情况
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"结果_{ts}.xlsx"
```

**Step 2**：修改 `backend/app/services/agent.py`：

**关键说明**：`save_message` **不**在 agent.py 调用，而是在 `chat.py` SSE 消费端调用。所以 agent.py 的职责是在 yield event 时带上 `output_display_name`。

`agent.py:241-254` 有 `excel_files = [f for f in files if f.get("type") != "image"]`，当前只在 init 块内使用；要改成在 `run_agent` 函数顶层定义（或 modify/create 分支内重新计算 `[f for f in files if f.get("type") != "image"]`）。

- **modify 分支**（line 365-407）：在 `output_path = result["output_path"]` 之后：

```python
excel_input_list = [f for f in files if f.get("type") != "image"]
display_name = _compute_display_name("modify", excel_input_list, source_var=source)
```

修改两处 yield，加 `output_display_name`：

```python
yield {
    "type": "diff_review",
    "diff": diff_data,
    "output_path": output_path,
    "output_display_name": display_name,  # 新增
    "input_path": source_path,
    ...
}
# done 事件不需要带（因为 diff 流程 output_path=None）
yield {"type": "done", "output_path": None}
```

- **create 分支**（line 421-444）：在 `output_path = result["output_path"]` 之后：

```python
excel_input_list = [f for f in files if f.get("type") != "image"]
display_name = _compute_display_name("create", excel_input_list)

yield {"type": "output_ready", "output_path": output_path, "output_display_name": display_name}
yield {"type": "done", "output_path": output_path, "output_display_name": display_name}
```

**Step 3**：修改 `backend/app/api/chat.py`：

- 在事件循环里新增 `output_display_name` 变量捕获，跟 `output_path` 并行：

```python
output_path = None
output_display_name = None
```

- 在 `diff_review` 分支（line 102-120）存入 pending_diffs 时加字段：

```python
if event.get("type") == "diff_review":
    output_path = event.get("output_path") or output_path
    output_display_name = event.get("output_display_name") or output_display_name
    if conv_id:
        pending_diffs[conv_id] = {
            ...
            "output_path": event["output_path"],
            "output_display_name": event.get("output_display_name"),  # 新增
            ...
        }
```

- 在 `output_ready` 和 `done` 分支补充（line 134-137）：

```python
elif event["type"] == "output_ready":
    output_path = event.get("output_path")
    output_display_name = event.get("output_display_name") or output_display_name
elif event["type"] == "done":
    output_path = event.get("output_path") or output_path
    output_display_name = event.get("output_display_name") or output_display_name
```

- 最后 `save_message` 调用（line 143）传参：

```python
save_message(
    conv_id,
    "assistant",
    content=full_content or None,
    tool_calls=all_tool_calls or None,
    output_path=output_path,
    output_display_name=output_display_name,  # 新增
    error=error_msg,
)
```

**Step 4**：修改 `backend/app/api/diff.py` —— **本 Task 最关键的修复，闭环三条链路**：

#### 4.1 approve 流程读取 + 写回 + 返回 display_name + **保持 current_file.filename 稳定**

line 51-87 `approve_diff` 改为：

```python
pending = pending_diffs.pop(conv_id)
output_path = pending["output_path"]
output_display_name = pending.get("output_display_name")  # 新增
diff_data = pending["diff"]
user_message = pending.get("user_message", "")

summary_text = generate_operation_summary(user_message, diff_data)

state = conversation_state.setdefault(conv_id, {
    "operation_history": [],
    "current_file": None,
})
state["operation_history"].append(summary_text)

try:
    new_profile = profile_excel(output_path)
except Exception as e:
    logger.warning("重新profile失败: %s", e)
    new_profile = {}

# 关键：filename 稳定继承（不使用 UUID 磁盘名），path 更新为新输出
prev_filename = (
    state["current_file"]["filename"] if state.get("current_file")
    else (pending["files"][0]["filename"] if pending.get("files") else output_path.rsplit("/", 1)[-1])
)
state["current_file"] = {
    "file_id": f"result_{conv_id}_{len(state['operation_history'])}",
    "filename": prev_filename,   # 稳定继承
    "path": output_path,          # 新路径
    "type": "excel",
    "profile": new_profile,
}

# 写回数据库（含 display_name）
update_last_assistant_output(conv_id, output_path, output_display_name)

logger.info("Diff审批通过 conv=%s output=%s display=%s history_len=%d",
            conv_id, output_path, output_display_name, len(state["operation_history"]))

# 返回给前端，供 DiffReview.vue 立即下载
return {"output_path": output_path, "output_display_name": output_display_name}
```

#### 4.2 reject 重试流程带上 display_name（防重试后丢失）

line 127-138 `event_stream` 的 `diff_review` 拦截分支改为：

```python
if event.get("type") == "diff_review":
    pending_diffs[conv_id] = {
        "messages": event["messages"],
        "diff": event["diff"],
        "output_path": event["output_path"],
        "output_display_name": event.get("output_display_name"),  # 新增
        "input_path": event["input_path"],
        "file_paths": event["file_paths"],
        "files": event.get("files", files),
        "user_message": saved_user_message,
        "retry_count": saved_retry_count,
    }
    frontend_event = {
        "type": "diff_review",
        "diff": event["diff"],
    }
    yield f"data: {json.dumps(frontend_event, ensure_ascii=False)}\n\n"
```

**Step 5**：Commit

```bash
git add backend/app/services/agent.py backend/app/api/chat.py backend/app/api/diff.py
git commit -m "feat(download): agent/chat/diff 链路透传 display_name + current_file filename 稳定继承"
```

---

## Task 4: `download.py` 支持 display_name

**Files**: `backend/app/api/download.py`

**Step 1**：改 handler 签名加 display_name：

```python
@router.get("/download")
async def download_file(filename: str, token: str = "", display_name: str = ""):
    # ... 已有鉴权 / is_active 检查 / 路径校验 ...

    file_path = WORK_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")

    # 下载时的显示名优先用 display_name，fallback 到原 filename
    download_name = display_name or filename

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

**Step 2**：Commit

```bash
git add backend/app/api/download.py
git commit -m "feat(download): 下载端点支持 display_name 覆盖"
```

---

## Task 5: 前端 download + message 透传

**Files**:
- `frontend/src/api/index.js`
- `frontend/src/composables/useChat.js`
- `frontend/src/components/MessageBubble.vue`

**Step 1**：`api/index.js` 的 `downloadFile` 加参数：

```js
export async function downloadFile(path, displayName = '') {
  const filename = path.split('/').pop()
  const token = localStorage.getItem('token')
  const params = new URLSearchParams({ filename, token })
  if (displayName) params.set('display_name', displayName)
  const response = await fetch(`/api/download?${params.toString()}`)
  if (!response.ok) throw new Error('下载失败')
  const blob = await response.blob()
  const reader = new FileReader()
  reader.onload = () => {
    const a = document.createElement('a')
    a.href = reader.result
    a.download = displayName || filename
    a.click()
  }
  reader.readAsDataURL(blob)
}
```

**Step 2**：`useChat.js` 三处需要映射 `output_display_name` → `outputDisplayName`：

- `handleEvent` 的 `output_ready` case（约 line 40）：同时设置 `assistantMsg.outputPath` 和 `assistantMsg.outputDisplayName = event.output_display_name`
- `handleEvent` 的 `done` case（约 line 45）：同样两个字段
- `loadFromHistory`（约 line 137）：`outputDisplayName: m.output_display_name || null`
- 初始化 assistantMsg 的地方（约 line 74 / 98）：`outputDisplayName: null`

**Step 4**：`MessageBubble.vue` 的 `handleDownload` 改为：

```js
async function handleDownload(path, displayName) {
  try {
    await downloadFile(path, displayName)
  } catch {
    alert('下载失败，请重试')
  }
}
```

模板里把当前的 `@click="handleDownload(message.outputPath)"` 改为 `@click="handleDownload(message.outputPath, message.outputDisplayName)"`。按钮的文字（line ~136 "下载结果文件"）可以改为动态：`{{ message.outputDisplayName || '下载结果文件' }}`，让用户提前看到下载文件名。

**Step 5**：`MessageBubble.vue` 的 `onDiffApproved` 扩展，接收并存入 display_name：

line 184 原：
```js
function onDiffApproved(outputPath) {
  props.message.outputPath = outputPath
  props.message.diff = null
}
```

改为：
```js
function onDiffApproved(outputPath, displayName) {
  props.message.outputPath = outputPath
  props.message.outputDisplayName = displayName
  props.message.diff = null
}
```

**Step 6**：`DiffReview.vue` 的 `handleApprove`（line 164-181）改：

```js
async function handleApprove() {
  if (!props.conversationId) return
  approving.value = true
  try {
    const result = await approveDiff(props.conversationId)
    if (result.output_path) {
      approved.value = true
      emit('approved', result.output_path, result.output_display_name)
      await downloadFile(result.output_path, result.output_display_name)
    } else if (result.error) {
      alert(result.error)
    }
  } catch (e) {
    alert('审批失败，请重试')
  } finally {
    approving.value = false
  }
}
```

注意 `emit('approved', ...)` 现在是两个参数；MessageBubble 的 `@approved="onDiffApproved"` 会自动把两个参数传给 handler。

**Step 7**：`npm run build` 零错误

**Step 8**：Commit

```bash
git add frontend/src/api/index.js frontend/src/composables/useChat.js frontend/src/components/MessageBubble.vue frontend/src/components/DiffReview.vue
git commit -m "feat(download): 前端下载透传 display_name（含审批后首次下载闭环 + SSE/history）"
```

---

## Task 6: `conversations.py` 管理员全局 scope

**Files**: `backend/app/api/conversations.py`

**Step 1**：改 `list_conversations`：

```python
from typing import Optional

@router.get("")
async def list_conversations(
    scope: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    conn = get_db()
    if scope == "all" and user.get("is_admin"):
        rows = conn.execute(
            """SELECT c.id, c.title, c.created_at, c.updated_at, c.user_id,
                      u.username AS owner_username,
                      (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) AS message_count,
                      (SELECT COUNT(*) FROM conversation_files WHERE conversation_id = c.id) AS file_count
               FROM conversations c
               LEFT JOIN users u ON c.user_id = u.id
               ORDER BY c.updated_at DESC"""
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user["user_id"],),
        ).fetchall()
    conn.close()
    return {"conversations": [dict(r) for r in rows]}
```

**Step 2**：改 `get_messages`：管理员绕过 user_id 检查：

```python
@router.get("/{conv_id}/messages")
async def get_messages(conv_id: str, user: dict = Depends(get_current_user)):
    conn = get_db()
    if user.get("is_admin"):
        conv = conn.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    else:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user["user_id"]),
        ).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(404, "对话不存在")
    # ... 剩下逻辑不变
```

**Step 3**：改 `delete_conversation`：

```python
@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    conn = get_db()
    if user.get("is_admin"):
        conv = conn.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,)).fetchone()
    else:
        conv = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user["user_id"]),
        ).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(404, "对话不存在")
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
```

**Step 4**：本地 curl 验证

```bash
# 用管理员 token
ADMIN_TOKEN=$(curl -s -X POST http://127.0.0.1:8911/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s "http://127.0.0.1:8911/api/conversations?scope=all" -H "Authorization: Bearer $ADMIN_TOKEN" | python -m json.tool | head -30
```

Expected：返回所有对话，含 `owner_username`、`message_count`、`file_count`

**Step 5**：Commit

```bash
git add backend/app/api/conversations.py
git commit -m "feat(admin): conversations 支持 scope=all + 管理员全局访问"
```

---

## Task 7: 前端 API 扩展

**Files**: `frontend/src/api/index.js`

**Step 1**：修改 `listConversations` 支持 scope：

```js
export async function listConversations(scope = '') {
  const params = scope ? { scope } : {}
  const { data } = await api.get('/conversations', { params })
  return data.conversations
}
```

**Step 2**：Commit

```bash
git add frontend/src/api/index.js
git commit -m "feat(admin): listConversations 支持 scope 参数"
```

---

## Task 8: `ConversationPreviewModal.vue` 新建

**Files**: 新建 `frontend/src/components/settings/ConversationPreviewModal.vue`

```vue
<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    @click.self="$emit('close')"
  >
    <div
      class="rounded-2xl shadow-xl w-full max-w-4xl mx-4 flex flex-col"
      :style="{ background: 'var(--surface)', maxHeight: '85vh' }"
    >
      <!-- 头部 -->
      <div class="px-6 py-4 border-b flex items-center justify-between" :style="{ borderColor: 'var(--border)' }">
        <div>
          <h3 class="text-base font-semibold" :style="{ color: 'var(--text)' }">
            {{ conversation?.title || '未命名对话' }}
          </h3>
          <p class="text-sm mt-0.5" :style="{ color: 'var(--text-muted)' }">
            <span class="inline-flex items-center gap-1">
              <User class="w-3.5 h-3.5" />
              {{ conversation?.owner_username }}
            </span>
            <span class="mx-2">·</span>
            <span>更新于 {{ formatTime(conversation?.updated_at) }}</span>
          </p>
        </div>
        <button
          @click="$emit('close')"
          class="p-1.5 rounded-lg hover:opacity-70 transition-opacity"
          :style="{ color: 'var(--text-muted)' }"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- 内容区（滚动） -->
      <div class="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        <!-- 附件 -->
        <div v-if="files.length" class="space-y-2">
          <h4 class="text-[13px] font-medium flex items-center gap-1.5" :style="{ color: 'var(--text-muted)' }">
            <Paperclip class="w-3.5 h-3.5" /> 附件（{{ files.length }}）
          </h4>
          <div class="space-y-1">
            <div
              v-for="f in files"
              :key="f.file_id"
              class="text-[13px] px-3 py-2 rounded-lg"
              :style="{ background: 'var(--background)', color: 'var(--text)' }"
            >
              📎 {{ f.filename }}
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div class="space-y-3">
          <h4 class="text-[13px] font-medium" :style="{ color: 'var(--text-muted)' }">
            消息记录（{{ messages.length }}）
          </h4>
          <div
            v-for="m in messages"
            :key="m.id"
            class="rounded-xl px-4 py-3"
            :style="{
              background: m.role === 'user' ? 'var(--primary-muted)' : 'var(--background)',
            }"
          >
            <div class="flex items-center gap-2 text-[12px] mb-1.5" :style="{ color: 'var(--text-muted)' }">
              <span class="font-medium" :style="{ color: 'var(--text)' }">
                {{ m.role === 'user' ? '👤 用户' : '🤖 助手' }}
              </span>
              <span>·</span>
              <span>{{ formatTime(m.created_at) }}</span>
            </div>
            <div v-if="m.content" class="text-[14px] whitespace-pre-wrap" :style="{ color: 'var(--text)' }">
              {{ m.content }}
            </div>
            <div v-if="m.output_path" class="mt-2">
              <button
                @click="handleDownload(m.output_path, m.output_display_name)"
                class="inline-flex items-center gap-1.5 text-[13px] px-3 py-1.5 rounded-lg transition-colors"
                :style="{ background: 'var(--primary)', color: 'white' }"
              >
                <Download class="w-3.5 h-3.5" />
                {{ m.output_display_name || '下载结果' }}
              </button>
            </div>
            <div v-if="m.error" class="mt-2 text-[13px]" :style="{ color: 'var(--error-emphasis)' }">
              ❌ {{ m.error }}
            </div>
          </div>
          <div v-if="!messages.length" class="text-[13px] py-8 text-center" :style="{ color: 'var(--text-muted)' }">
            暂无消息
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { User, X, Paperclip, Download } from 'lucide-vue-next'
import { getConversationMessages, downloadFile } from '../../api'

const props = defineProps({
  conversation: { type: Object, default: null }
})
defineEmits(['close'])

const messages = ref([])
const files = ref([])

watch(() => props.conversation, async (conv) => {
  if (!conv) return
  try {
    const data = await getConversationMessages(conv.id)
    messages.value = data.messages || []
    files.value = data.files || []
  } catch {
    messages.value = []
    files.value = []
  }
}, { immediate: true })

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay} 天前`
  return d.toLocaleDateString('zh-CN')
}

async function handleDownload(path, displayName) {
  try {
    await downloadFile(path, displayName)
  } catch {
    alert('下载失败')
  }
}
</script>
```

**Step 2**：Commit

```bash
git add frontend/src/components/settings/ConversationPreviewModal.vue
git commit -m "feat(admin): ConversationPreviewModal 对话预览弹窗"
```

---

## Task 9: `AdminConversationsPanel.vue` 新建

**Files**: 新建 `frontend/src/components/settings/AdminConversationsPanel.vue`

```vue
<template>
  <section class="space-y-4">
    <div class="flex items-center gap-2">
      <Database class="w-[18px] h-[18px]" :style="{ color: 'var(--primary)' }" />
      <h2 class="text-base font-semibold" :style="{ color: 'var(--text)' }">全局对话管理</h2>
      <span
        class="text-[11px] font-medium px-2 py-0.5 rounded"
        :style="{ background: 'var(--primary-muted)', color: 'var(--primary)' }"
      >仅管理员</span>
    </div>

    <p class="text-[13px]" :style="{ color: 'var(--text-muted)' }">
      共 {{ conversations.length }} 条对话，来自 {{ uniqueUserCount }} 个用户
    </p>

    <!-- 表格容器，宽度撑满 -->
    <div class="rounded-xl overflow-hidden border" :style="{ borderColor: 'var(--border)' }">
      <table class="w-full text-[13px]">
        <thead :style="{ background: 'var(--background)' }">
          <tr>
            <th class="px-4 py-3 text-left font-medium" :style="{ color: 'var(--text-muted)' }">用户</th>
            <th class="px-4 py-3 text-left font-medium" :style="{ color: 'var(--text-muted)' }">对话标题</th>
            <th class="px-4 py-3 text-left font-medium" :style="{ color: 'var(--text-muted)' }">更新时间</th>
            <th class="px-4 py-3 text-center font-medium" :style="{ color: 'var(--text-muted)' }">消息</th>
            <th class="px-4 py-3 text-center font-medium" :style="{ color: 'var(--text-muted)' }">文件</th>
            <th class="px-4 py-3 text-right font-medium" :style="{ color: 'var(--text-muted)' }">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in conversations"
            :key="c.id"
            class="border-t transition-colors hover:opacity-90"
            :style="{ borderColor: 'var(--border)' }"
          >
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium"
                :style="{ background: 'var(--primary)', color: 'white' }"
              >
                <User class="w-3 h-3" />
                {{ c.owner_username }}
              </span>
            </td>
            <td class="px-4 py-3" :style="{ color: 'var(--text)' }">
              {{ c.title || '未命名对话' }}
            </td>
            <td class="px-4 py-3" :style="{ color: 'var(--text-muted)' }">
              {{ formatTime(c.updated_at) }}
            </td>
            <td class="px-4 py-3 text-center">
              <span
                class="inline-block px-2 py-0.5 rounded text-[11px]"
                :style="{ background: 'var(--background)', color: 'var(--text-muted)' }"
              >{{ c.message_count }}</span>
            </td>
            <td class="px-4 py-3 text-center">
              <span
                class="inline-block px-2 py-0.5 rounded text-[11px]"
                :style="{ background: 'var(--background)', color: 'var(--text-muted)' }"
              >{{ c.file_count }}</span>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center justify-end gap-2">
                <button
                  @click="preview = c"
                  class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
                  :style="{ background: 'var(--primary)', color: 'white' }"
                >查看</button>
                <button
                  @click="handleDelete(c)"
                  class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
                  :style="{ background: 'var(--error-subtle)', color: 'var(--error-emphasis)' }"
                >删除</button>
              </div>
            </td>
          </tr>
          <tr v-if="!conversations.length">
            <td colspan="6" class="px-4 py-8 text-center" :style="{ color: 'var(--text-muted)' }">
              暂无对话
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConversationPreviewModal
      v-if="preview"
      :conversation="preview"
      @close="preview = null"
    />
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Database, User } from 'lucide-vue-next'
import { listConversations, deleteConversation } from '../../api'
import ConversationPreviewModal from './ConversationPreviewModal.vue'

const conversations = ref([])
const preview = ref(null)

const uniqueUserCount = computed(() => {
  const set = new Set(conversations.value.map(c => c.owner_username))
  return set.size
})

async function load() {
  try {
    conversations.value = await listConversations('all')
  } catch { conversations.value = [] }
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  const now = new Date()
  const diffMin = Math.floor((now - d) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay} 天前`
  return d.toLocaleDateString('zh-CN')
}

async function handleDelete(c) {
  if (!confirm(`确定删除 ${c.owner_username} 的对话 "${c.title}" 吗？`)) return
  try {
    await deleteConversation(c.id)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

onMounted(load)
</script>
```

**Step 2**：`npm run build` 零错误

**Step 3**：Commit

```bash
git add frontend/src/components/settings/AdminConversationsPanel.vue
git commit -m "feat(admin): AdminConversationsPanel 全局对话管理表格"
```

---

## Task 10: `SettingsPage.vue` 接入

**Files**: `frontend/src/components/SettingsPage.vue`

**Step 1**：import + 模板加一个新 section（放在 UserManagement 之后、ChangePassword 之前）：

```vue
<div v-if="isAdmin" class="h-px" style="background: var(--border)" />
<AdminConversationsPanel v-if="isAdmin" />
```

import：

```js
import AdminConversationsPanel from './settings/AdminConversationsPanel.vue'
```

**Step 2**：`npm run build`

**Step 3**：Commit

```bash
git add frontend/src/components/SettingsPage.vue
git commit -m "feat(admin): SettingsPage 接入全局对话管理面板"
```

---

## Task 11: 部署 NAS

**Step 1**：scp 所有改动文件

```bash
cd ~/Desktop/Excel
tar cf - \
  backend/app/database.py \
  backend/app/api/conversations.py \
  backend/app/api/download.py \
  backend/app/api/diff.py \
  backend/app/api/chat.py \
  backend/app/services/agent.py \
  frontend/src/api/index.js \
  frontend/src/composables/useChat.js \
  frontend/src/components/MessageBubble.vue \
  frontend/src/components/DiffReview.vue \
  frontend/src/components/SettingsPage.vue \
  frontend/src/components/settings/ConversationPreviewModal.vue \
  frontend/src/components/settings/AdminConversationsPanel.vue \
  | SSHPASS='theendqq123' sshpass -e ssh admin@192.168.124.3 "cd /home/admin/excel && tar xvf -"
```

**Step 2**：rebuild

```bash
SSHPASS='theendqq123' sshpass -e ssh admin@192.168.124.3 "cd /home/admin/excel && echo 'theendqq123' | sudo -S docker compose up -d --build"
```

**Step 3**：生产验证

- 管理员登录 → 设置页看到"全局对话管理"表格
- 表格清晰展示 用户 / 标题 / 时间 / 消息数 / 文件数
- 点查看可弹出消息预览
- **下载命名 3 条闭环链路都要验证**：
  - ✅ modify 首轮审批通过后直接下载，文件名是 `原名_已修改.xlsx`
  - ✅ 历史消息点下载按钮，文件名正确
  - ✅ modify **驳回重试后** 再审批，文件名仍然是 `原名_已修改.xlsx`（没退化成 UUID）
- create 流程：下载文件名是 `原名_汇总.xlsx` 或 `结果_时间戳.xlsx`
- **多轮 modify 验证**：同一对话第一轮修改 → 审批 → 第二轮继续修改 → 审批 → 下载文件名仍然是 `原名_已修改.xlsx`（filename 稳定继承）

**Step 4**：commit message（如果有小修，无则跳过）

---

## 完成标准

- ✅ 数据库迁移无损（messages 加 output_display_name）
- ✅ modify/create 两种模式下载都用新名
- ✅ 管理员设置页表格**清晰易读**（用户 Badge 高对比、消息文件数 badge、相对时间）
- ✅ 管理员可预览任意对话
- ✅ 管理员可删除任意对话
- ✅ npm run build 零错误
- ✅ NAS 部署后功能完整

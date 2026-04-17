# 下载文件重命名 + 管理员全局对话管理 设计

**日期**：2026-04-17
**状态**：用户已确认

## 需求

1. **下载文件显示名优化**：目前下载结果文件名是 `result_abc12345.xlsx`（UUID 生成的"乱码"），要改为基于用户上传文件名的有意义名字。
2. **管理员看所有用户的对话和文件**：用于后期数据管理，在设置页独立 section 展示表格视图，UI 要**清晰可见**。

## 方案 1：下载重命名

### 命名规则

- **modify 模式**（修改已有文件）：`{原文件名无扩展}_已修改.xlsx`
  - 例：`销售报表.xlsx` → `销售报表_已修改.xlsx`
- **create 模式**（新建文件）：
  - 有输入：`{首个输入文件名无扩展}_汇总.xlsx`
  - 无输入：`结果_{YYYYMMDD_HHMMSS}.xlsx`

### 技术路径

**磁盘文件名保持 `result_{id}.xlsx` 不变**（避免碰撞），只改下载时浏览器显示名。

1. **DB 迁移**：`messages` 表新增 `output_display_name TEXT` 列
2. **后端生成**：`agent.py` 在 `output_path` 设置处同步计算 `display_name`，通过 `save_message` 写入；approve 流程的 `update_last_assistant_output` 也要带上 `display_name`
3. **后端下载**：`/api/download?filename=X&display_name=Y` 用 `display_name` 作 `FileResponse(filename=...)`，自动处理 UTF-8（`filename*=UTF-8''` 编码）
4. **前端**：`get_messages` 返回包含 `output_display_name`；`downloadFile(path, displayName)` 加参数；`MessageBubble.handleDownload` 透传

### 来源识别

- modify 模式：从 tool call args 的 `source` 字段（如 `INPUT_PATH_1`）→ 对应到 `files` 参数里的第 N 个 excel 文件 → 取 `filename`
- create 模式：从 `files` 取第一个 excel 文件的 `filename`；无输入 → 时间戳名

### 多轮对话命名稳定性（关键设计）

**问题**：`diff.py approve` 当前把 `state["current_file"]["filename"]` 设为 `output_path.rsplit("/", 1)[-1]` = `result_xxx.xlsx`（UUID 磁盘名），第二轮起 agent 的 `files` 参数里 filename 就是乱码，会退化为 `result_xxx_已修改.xlsx`。

**解决**：审批通过时 `current_file.filename` **继承上一轮的 filename**（= 最初的上传 filename），只更新 `path`。filename 字段表达"语义来源"而非"磁盘路径"：

```python
# 原代码（会退化）
state["current_file"] = {
    "filename": output_path.rsplit("/", 1)[-1],  # "result_xxx.xlsx"
    ...
}

# 改为（稳定）
prev_filename = (
    state["current_file"]["filename"] if state.get("current_file")
    else pending["files"][0]["filename"]  # 首次审批：取原始上传名
)
state["current_file"] = {
    "filename": prev_filename,  # "销售.xlsx" 链式稳定
    "path": output_path,         # 但 path 指向新输出
    ...
}
```

这样递归下来，无论经过多少轮 modify，`filename` 始终是最初的 `销售.xlsx`，每轮 display_name 都是 `销售_已修改.xlsx`。浏览器对同名文件会自动加 `(1)(2)` 后缀，可接受。

_compute_display_name 不需要剥后缀逻辑。

## 方案 2：管理员全局对话管理

### UI 设计（重点：清晰可见）

设置页新增"全局对话管理"section（仅管理员可见），采用表格布局：

```
┌ 全局对话管理 ──────────────────────────────────── [仅管理员] ┐
│                                                             │
│ 共 X 条对话，来自 Y 个用户                                   │
│                                                             │
│ ┌───────────┬──────────────────┬──────────┬─────┬─────┬─────┐
│ │ 用户      │ 对话标题         │ 更新时间  │ 消息│ 文件│ 操作│
│ ├───────────┼──────────────────┼──────────┼─────┼─────┼─────┤
│ │ 👤 admin  │ 销售报表处理     │ 2 小时前 │ 12  │ 2   │ ⋯   │
│ │ 👤 alice  │ 预算对账         │ 昨天     │ 8   │ 1   │ ⋯   │
│ │ 👤 bob    │ Q1 汇总          │ 3 天前   │ 5   │ 3   │ ⋯   │
│ └───────────┴──────────────────┴──────────┴─────┴─────┴─────┘
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**清晰度要点（CLAUDE.md 规范 + 用户强调）**：
- 用户列用 Badge 样式（主色背景，白字），一眼可辨
- 时间用**相对时间**（"2 小时前"/"昨天"），而不是 ISO 时间戳
- 消息数 / 文件数作为灰色 badge，有视觉层级
- 操作列：**[查看]**（主色按钮）+ **[删除]**（红色/灰色按钮，小，二次确认）
- 每行 hover 高亮
- 空态：`暂无对话` + 图标
- 表格宽度撑满，不紧凑

### 查看弹窗

点"查看"按钮 → 大弹窗（最大 max-w-4xl，高度 ~80vh）：

```
┌ [对话标题] by @username ──────────────── [✕] ┐
│                                             │
│ 创建时间: 2026-04-15 10:23                  │
│ 更新时间: 2026-04-17 14:05                  │
│                                             │
│ 📎 附件（3）                                 │
│  • 销售.xlsx（2024 Q3）                     │
│  • 对账.xlsx                                │
│                                             │
│ 💬 消息记录                                  │
│  ┌─────────────────────────────┐           │
│  │ 👤 user  ·  10:23           │           │
│  │ 请把销售.xlsx 按地区合并    │           │
│  └─────────────────────────────┘           │
│  ┌─────────────────────────────┐           │
│  │ 🤖 assistant ·  10:24       │           │
│  │ 好的，已经按地区合并...     │           │
│  │ ⬇ 下载：销售_已修改.xlsx    │           │
│  └─────────────────────────────┘           │
│                                             │
└─────────────────────────────────────────────┘
```

只读预览。不复用 MessageBubble（避免污染 useChat state），做一个简单的 `ConversationPreviewModal.vue`，展示文字+下载链接。

### 后端改动

1. `GET /api/conversations?scope=all`：管理员可传 `scope=all` 获取所有对话；默认（无 scope 或 scope=mine）只返回自己的。返回字段加 `owner_username` + `message_count` + `file_count`（通过 COUNT subquery 一次查完）
2. `GET /api/conversations/{id}/messages`：管理员绕过 user_id 检查
3. `DELETE /api/conversations/{id}`：管理员绕过 user_id 检查

### 权限 & 安全

- 管理员可下载任意对话的结果文件。**注意现状**：`/api/download` 目前只校验 JWT + is_active，不校验文件归属——任何已登录有效用户，只要知道磁盘文件名都可下载。这是**本次接受的既有现状**（YAGNI），本次 NOT 改文件归属校验。若将来有隐私隔离需求，需单独一轮改造：下载端点加入"文件所属 conversation 所属 user_id" 校验（非 admin 只能下载自己对话的文件）。
- 管理员可删除任意对话（级联删消息 `ON DELETE CASCADE` 已有）
- 不实现"用户操作日志"（YAGNI，管理员主动操作，不需要审计）

## 非目标（不做）

- 不提供管理员编辑其他用户消息（只读 + 删除对话够了）
- 不做对话搜索（列表量不大时无必要；后期需要再加）
- 不做分页（百条以内直接列完；后期需要再加）
- 不改磁盘文件命名
- 不做审计日志

## 部署影响

- DB 迁移：`messages` 表加 `output_display_name` 列，用 PRAGMA 检查 + ALTER TABLE（同样的兼容模式）
- 无破坏性：老消息 `output_display_name` 为 NULL，前端下载时 fallback 到原 filename

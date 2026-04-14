# 结果文件预览功能设计

## 需求

- AI 处理完成后，在下载按钮旁加"预览"按钮，点击弹出 Modal 查看结果 Excel 内容
- 对话历史中也能回看之前生成的结果文件
- 复用现有 `ExcelPreview.vue` 弹窗样式，预览行数提升到 200 行

## 方案：新增独立的结果文件预览端点

结果文件不是用户上传的，不应混入 `uploaded_files` 字典。新建独立端点，概念清晰，改动最小。

## 详细设计

### 后端

- 新端点：`GET /api/files/preview-output?filename=xxx`
- 复用 `preview_excel(path, max_rows=200)`
- 安全校验：同 download 端点的文件名校验逻辑（防路径遍历，禁止 `/`、`..`）
- 需要 JWT 认证

### 前端

- `ExcelPreview.vue` 增加可选 prop `outputFilename`，与 `fileId` 二选一
  - 有 `fileId` → 调 `getExcelPreview(fileId)`（现有）
  - 有 `outputFilename` → 调 `getOutputPreview(filename)`（新增）
- `MessageBubble.vue` 下载按钮旁加"预览"按钮，点击打开 ExcelPreview
- `api/index.js` 新增 `getOutputPreview(filename)` 方法

### 改动文件清单

1. `backend/app/api/files.py` — 加 preview-output 端点
2. `frontend/src/api/index.js` — 加 getOutputPreview 方法
3. `frontend/src/components/common/ExcelPreview.vue` — 支持双数据源（fileId / outputFilename）
4. `frontend/src/components/MessageBubble.vue` — 加预览按钮 + ExcelPreview 弹窗

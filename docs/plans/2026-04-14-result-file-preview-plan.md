# 结果文件预览 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在下载按钮旁增加"预览"按钮，点击弹出 Modal 查看 AI 生成的结果 Excel 文件内容（200 行），对话历史中也可回看。

**Architecture:** 新增 `GET /api/files/preview-output` 端点，接收文件名参数，直接从 WORK_DIR 读取结果文件并返回预览数据。前端复用 `ExcelPreview.vue`，通过新增可选 prop 支持按文件名获取预览。

**Tech Stack:** FastAPI, pandas, Vue 3, axios

---

### Task 1: 后端 — 新增结果文件预览端点

**Files:**
- Modify: `backend/app/api/files.py`

**Step 1: 在 `files.py` 末尾（`delete_file` 之前）添加 preview-output 端点**

在 `@router.delete("/{file_id}")` 之前插入：

```python
@router.get("/preview-output")
async def preview_output_file(filename: str, user: dict = Depends(get_current_user)):
    """预览 AI 生成的结果文件（前 200 行）"""
    import re
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "非法文件名")
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
        raise HTTPException(400, "非法文件名")
    file_path = WORK_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{ext}" in IMAGE_EXTS:
        raise HTTPException(400, "图片文件不支持表格预览")
    try:
        data = preview_excel(str(file_path), max_rows=200)
    except Exception as e:
        raise HTTPException(500, f"预览失败: {str(e)}")
    return {"sheets": data}
```

**Step 2: 验证后端启动无语法错误**

Run: `cd ~/Desktop/Excel && docker compose up -d --build`（或本地 `python -c "from app.api.files import router"`）

**Step 3: Commit**

```bash
git add backend/app/api/files.py
git commit -m "feat: 新增结果文件预览端点 GET /api/files/preview-output"
```

---

### Task 2: 前端 API — 新增 getOutputPreview 方法

**Files:**
- Modify: `frontend/src/api/index.js`

**Step 1: 在 `getExcelPreview` 函数后面添加新方法**

在第 49 行 `}` 之后插入：

```javascript
export async function getOutputPreview(filename) {
  const { data } = await api.get('/files/preview-output', { params: { filename } })
  return data.sheets
}
```

**Step 2: Commit**

```bash
git add frontend/src/api/index.js
git commit -m "feat: 新增 getOutputPreview API 方法"
```

---

### Task 3: ExcelPreview 组件 — 支持双数据源

**Files:**
- Modify: `frontend/src/components/ExcelPreview.vue`

**Step 1: 修改 props 定义，`fileId` 改为可选，新增 `outputFilename`**

将 props 从：
```javascript
const props = defineProps({
  fileId: { type: String, required: true },
  filename: { type: String, required: true },
})
```

改为：
```javascript
const props = defineProps({
  fileId: { type: String, default: '' },
  outputFilename: { type: String, default: '' },
  filename: { type: String, required: true },
})
```

**Step 2: import 新增 `getOutputPreview`**

将：
```javascript
import { getExcelPreview } from '../api'
```

改为：
```javascript
import { getExcelPreview, getOutputPreview } from '../api'
```

**Step 3: 修改 onMounted 逻辑，根据 prop 选择数据源**

将 onMounted 从：
```javascript
onMounted(async () => {
  try {
    sheets.value = await getExcelPreview(props.fileId)
    const names = Object.keys(sheets.value)
    if (names.length) activeSheet.value = names[0]
  } catch (e) {
    error.value = e.response?.data?.detail || '预览加载失败'
  } finally {
    loading.value = false
  }
})
```

改为：
```javascript
onMounted(async () => {
  try {
    if (props.outputFilename) {
      sheets.value = await getOutputPreview(props.outputFilename)
    } else {
      sheets.value = await getExcelPreview(props.fileId)
    }
    const names = Object.keys(sheets.value)
    if (names.length) activeSheet.value = names[0]
  } catch (e) {
    error.value = e.response?.data?.detail || '预览加载失败'
  } finally {
    loading.value = false
  }
})
```

**Step 4: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`

**Step 5: Commit**

```bash
git add frontend/src/components/ExcelPreview.vue
git commit -m "feat: ExcelPreview 支持通过 outputFilename 预览结果文件"
```

---

### Task 4: MessageBubble — 添加预览按钮

**Files:**
- Modify: `frontend/src/components/MessageBubble.vue`

**Step 1: 在 `<script setup>` 中添加状态和 import**

在 import 行添加 `Eye` 图标：
```javascript
import { Search, Play, Download, ChevronDown, Eye } from 'lucide-vue-next'
```

添加 ExcelPreview 组件导入：
```javascript
import ExcelPreview from './ExcelPreview.vue'
```

添加预览状态 ref：
```javascript
const showPreview = ref(false)
```

确保 `ref` 已从 vue 导入（当前只有 `computed, reactive`，需加 `ref`）：
```javascript
import { computed, reactive, ref } from 'vue'
```

**Step 2: 在模板中，下载按钮旁添加预览按钮**

将下载按钮区域（第 129-137 行）从：
```html
      <!-- 下载按钮（审批通过后 或 create 模式） -->
      <button
        v-if="message.outputPath"
        @click="handleDownload(message.outputPath)"
        class="inline-flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] hover:bg-[#333] text-white text-sm font-medium rounded-xl transition-colors cursor-pointer"
      >
        <Download class="w-4 h-4" />
        下载结果文件
      </button>
```

改为：
```html
      <!-- 下载 + 预览按钮（审批通过后 或 create 模式） -->
      <div v-if="message.outputPath" class="flex items-center gap-2">
        <button
          @click="handleDownload(message.outputPath)"
          class="inline-flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] hover:bg-[#333] text-white text-sm font-medium rounded-xl transition-colors cursor-pointer"
        >
          <Download class="w-4 h-4" />
          下载结果文件
        </button>
        <button
          @click="showPreview = true"
          class="inline-flex items-center gap-2 px-4 py-2 border border-[#e5e5e5] hover:bg-[#f4f4f4] text-[#555] text-sm font-medium rounded-xl transition-colors cursor-pointer"
        >
          <Eye class="w-4 h-4" />
          预览
        </button>
      </div>
```

**Step 3: 在模板末尾（`</div>` 关闭 AI 消息之前）添加 ExcelPreview 弹窗**

在错误区域的 `</div>` 之后、AI 消息的 `</div>` 之前添加：
```html
      <!-- 结果文件预览弹窗 -->
      <ExcelPreview
        v-if="showPreview && message.outputPath"
        :outputFilename="message.outputPath.split('/').pop()"
        :filename="message.outputPath.split('/').pop()"
        @close="showPreview = false"
      />
```

**Step 4: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`

**Step 5: Commit**

```bash
git add frontend/src/components/MessageBubble.vue
git commit -m "feat: 结果文件预览按钮，点击弹出 ExcelPreview 弹窗"
```

---

### Task 5: 构建部署 + 端到端验证

**Step 1: 前端构建输出到 backend/static/**

Run: `cd ~/Desktop/Excel/frontend && npm run build`

**Step 2: Docker 构建部署**

Run: `cd ~/Desktop/Excel && docker compose up -d --build`

**Step 3: 端到端验证清单**

1. 上传一个 Excel 文件，发送处理请求
2. AI 处理完成后，确认下载按钮旁出现"预览"按钮
3. 点击"预览"，确认弹出 Modal，显示最多 200 行数据
4. 切换 Sheet 标签（如有多个 Sheet）
5. 关闭弹窗，点击下载，确认下载功能不受影响
6. 刷新页面，进入对话历史，确认"预览"按钮仍可用

**Step 4: Commit 构建产物**

```bash
git add backend/static/
git commit -m "build: 构建前端静态文件"
```

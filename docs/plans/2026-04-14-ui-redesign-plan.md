# Excel Agent 前端 UI 重构实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 对标 Claude/ChatGPT 重构前端界面 — 首页/对话双模式、可收起侧边栏、三层输入框、设置独立页面、全面组件化。

**Architecture:** 方案 A（双模式视图）— ChatPanel 通过 `hasMessages` 状态在首页模式和对话模式间切换。侧边栏通过 `useSidebar` composable 控制收起/展开。设置页替代设置弹窗，通过 App.vue 的 `currentView` 状态切换。所有色值通过 CSS 变量定义，组件模板不超过 150 行。

**Tech Stack:** Vue 3 (Composition API) + Tailwind CSS 4 + Vite 6 + lucide-vue-next

**设计稿:** `/Users/lin/Desktop/Excel/ui.pen`（通过 pencil MCP 工具查看）

**开发规范:** 见 `/Users/lin/Desktop/Excel/CLAUDE.md`

---

## Task 1: CSS 变量体系

**Files:**
- Modify: `frontend/src/styles/main.css`

**Step 1: 在 main.css 中添加 CSS 变量**

在 `@import "tailwindcss";` 之后、`body` 规则之前插入完整变量定义：

```css
@import "tailwindcss";

:root {
  /* Primary */
  --primary: #3B63C9;
  --primary-hover: #2B51B1;
  --primary-active: #223F8A;
  --primary-muted: #F0F4FF;
  --primary-ring: rgba(59, 99, 201, 0.25);
  --primary-foreground: #FFFFFF;

  /* Semantic — subtle bg + emphasis text */
  --success-subtle: #E6F9EE;
  --success-emphasis: #166534;
  --warning-subtle: #FFF8E6;
  --warning-emphasis: #854D0E;
  --error-subtle: #FEF2F2;
  --error-emphasis: #991B1B;
  --info-subtle: #F0F4FF;
  --info-emphasis: #3B63C9;

  /* Neutrals / Surfaces */
  --background: #F9FAFB;
  --surface: #FFFFFF;
  --elevated: #F3F4F6;
  --surface-hover: #E5E7EB;

  /* Text */
  --text: #111827;
  --text-secondary: #4B5563;
  --text-muted: #6B7280;
  --text-placeholder: #9CA3AF;

  /* Borders */
  --border: #E5E7EB;
  --border-strong: #D1D5DB;
  --input-border: #D1D5DB;

  /* Sidebar */
  --sidebar-width: 260px;
  --sidebar-bg: #FFFFFF;
  --sidebar-border: #E5E7EB;

  /* Transitions */
  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  color: var(--text);
  background: var(--background);
}
```

**Step 2: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功，无错误

**Step 3: Commit**

```bash
git add frontend/src/styles/main.css
git commit -m "feat: 添加 CSS 变量设计 token 体系"
```

---

## Task 2: useSidebar composable

**Files:**
- Create: `frontend/src/composables/useSidebar.js`

**Step 1: 创建 useSidebar**

```javascript
import { ref } from 'vue'

const collapsed = ref(false)

export function useSidebar() {
  function toggle() {
    collapsed.value = !collapsed.value
  }

  function collapse() {
    collapsed.value = true
  }

  function expand() {
    collapsed.value = false
  }

  return { collapsed, toggle, collapse, expand }
}
```

**Step 2: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/composables/useSidebar.js
git commit -m "feat: 添加 useSidebar composable 管理侧边栏收起/展开"
```

---

## Task 3: 侧边栏组件化 + 收起/展开

将现有 Sidebar.vue（124 行）拆分为 4 个组件。

**Files:**
- Create: `frontend/src/components/layout/SidebarHeader.vue`
- Create: `frontend/src/components/layout/ConversationList.vue`
- Create: `frontend/src/components/layout/SidebarFooter.vue`
- Rewrite: `frontend/src/components/Sidebar.vue`

**Step 1: 创建 layout 目录**

Run: `mkdir -p ~/Desktop/Excel/frontend/src/components/layout`

**Step 2: 创建 SidebarHeader.vue**

Logo 区域。不含新对话按钮（已移到 TopControls），不含搜索框（首轮不实现搜索，避免死 UI）。

```vue
<template>
  <div class="shrink-0 flex items-center gap-2 px-4 pt-4 pb-3">
    <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background: var(--primary)">
      <FileSpreadsheet class="w-4 h-4 text-white" />
    </div>
    <span class="text-[15px] font-semibold" style="color: var(--text)">Excel Agent</span>
  </div>
</template>

<script setup>
import { FileSpreadsheet } from 'lucide-vue-next'
</script>
```

**Step 3: 创建 ConversationList.vue**

对话列表 + 分组逻辑（从 Sidebar.vue 提取）。

```vue
<template>
  <div class="flex-1 overflow-y-auto px-2">
    <template v-for="group in groupedConversations" :key="group.label">
      <div class="px-2 py-1.5 text-xs font-medium mt-2 first:mt-0" style="color: var(--text-placeholder)">
        {{ group.label }}
      </div>
      <div
        v-for="conv in group.items"
        :key="conv.id"
        :class="[
          'group flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] cursor-pointer mb-0.5 transition-colors',
          currentConvId === conv.id
            ? 'font-medium'
            : ''
        ]"
        :style="{
          background: currentConvId === conv.id ? 'var(--surface-hover)' : 'transparent',
          color: currentConvId === conv.id ? 'var(--text)' : 'var(--text-secondary)'
        }"
        @click="$emit('select', conv.id)"
      >
        <MessageSquare class="w-3.5 h-3.5 shrink-0" />
        <span class="flex-1 truncate">{{ conv.title }}</span>
        <button
          @click.stop="$emit('delete', conv.id)"
          class="opacity-0 group-hover:opacity-100 p-0.5 rounded transition-all"
        >
          <Trash2 class="w-3.5 h-3.5" style="color: var(--text-placeholder)" />
        </button>
      </div>
    </template>
    <div
      v-if="conversations.length === 0 && !loading"
      class="px-3 py-8 text-center text-xs"
      style="color: var(--text-placeholder)"
    >
      暂无对话记录
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { MessageSquare, Trash2 } from 'lucide-vue-next'

const props = defineProps({
  conversations: { type: Array, default: () => [] },
  currentConvId: { type: [String, Number], default: null },
  loading: { type: Boolean, default: false }
})

defineEmits(['select', 'delete'])

const groupedConversations = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)

  const groups = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '最近 7 天', items: [] },
    { label: '更早', items: [] },
  ]

  for (const conv of props.conversations) {
    const date = new Date(conv.updated_at || conv.created_at)
    if (date >= today) groups[0].items.push(conv)
    else if (date >= yesterday) groups[1].items.push(conv)
    else if (date >= weekAgo) groups[2].items.push(conv)
    else groups[3].items.push(conv)
  }

  return groups.filter(g => g.items.length > 0)
})
</script>
```

**Step 4: 创建 SidebarFooter.vue**

用户信息 + 设置/退出按钮。

```vue
<template>
  <div class="shrink-0 p-3" style="border-top: 1px solid var(--sidebar-border)">
    <div class="flex items-center gap-2">
      <div
        class="w-7 h-7 rounded-full flex items-center justify-center"
        style="background: var(--surface-hover)"
      >
        <User class="w-4 h-4" style="color: var(--text-secondary)" />
      </div>
      <span class="flex-1 text-[13px] truncate" style="color: var(--text-secondary)">
        {{ username }}
      </span>
      <button
        @click="$emit('openSettings')"
        class="p-1 rounded-md transition-colors hover:bg-[var(--elevated)]"
        title="设置"
      >
        <Settings class="w-4 h-4" style="color: var(--text-placeholder)" />
      </button>
      <button
        @click="$emit('logout')"
        class="p-1 rounded-md transition-colors hover:bg-[var(--elevated)]"
        title="退出登录"
      >
        <LogOut class="w-4 h-4" style="color: var(--text-placeholder)" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { User, Settings, LogOut } from 'lucide-vue-next'

defineProps({
  username: { type: String, default: '' }
})

defineEmits(['openSettings', 'logout'])
</script>
```

**Step 5: 重写 Sidebar.vue 为容器组件**

```vue
<template>
  <aside
    class="h-full flex flex-col shrink-0 overflow-hidden transition-all"
    :style="{
      width: collapsed ? '0px' : 'var(--sidebar-width)',
      opacity: collapsed ? 0 : 1,
      background: 'var(--sidebar-bg)',
      borderRight: collapsed ? 'none' : '1px solid var(--sidebar-border)',
      transitionDuration: 'var(--duration-slow)'
    }"
  >
    <SidebarHeader />
    <ConversationList
      :conversations="conversations"
      :currentConvId="currentConvId"
      :loading="loading"
      @select="handleSelect"
      @delete="handleDelete"
    />
    <SidebarFooter
      :username="user?.username"
      @openSettings="$emit('openSettings')"
      @logout="handleLogout"
    />
  </aside>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuth } from '../composables/useAuth'
import { useConversations } from '../composables/useConversations'
import { useSidebar } from '../composables/useSidebar'
import SidebarHeader from './layout/SidebarHeader.vue'
import ConversationList from './layout/ConversationList.vue'
import SidebarFooter from './layout/SidebarFooter.vue'

const emit = defineEmits(['openSettings', 'selectConversation'])

const { user, logout } = useAuth()
const { conversations, currentConvId, loading, load, remove, select } = useConversations()
const { collapsed } = useSidebar()

function handleSelect(convId) {
  select(convId)
  emit('selectConversation', convId)
}

async function handleDelete(convId) {
  await remove(convId)
}

function handleLogout() {
  logout()
}

onMounted(() => {
  load()
})
</script>
```

**Step 6: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 7: Commit**

```bash
git add frontend/src/components/layout/ frontend/src/components/Sidebar.vue
git commit -m "refactor: 侧边栏组件化拆分 + 收起/展开支持"
```

---

## Task 4: TopControls 浮动控件

**Files:**
- Create: `frontend/src/components/layout/TopControls.vue`

**Step 1: 创建 TopControls.vue**

浮动在主内容区左上角和右上角的按钮。

```vue
<template>
  <div class="absolute top-0 left-0 right-0 flex items-center justify-between p-3 z-10 pointer-events-none">
    <button
      @click="toggle"
      class="p-1.5 rounded-lg transition-colors pointer-events-auto hover:bg-[var(--elevated)]"
      title="切换侧边栏"
    >
      <PanelLeft class="w-5 h-5" style="color: var(--text-muted)" />
    </button>
    <button
      @click="$emit('newChat')"
      class="p-1.5 rounded-lg transition-colors pointer-events-auto hover:bg-[var(--elevated)]"
      title="新对话"
    >
      <SquarePen class="w-5 h-5" style="color: var(--text-muted)" />
    </button>
  </div>
</template>

<script setup>
import { PanelLeft, SquarePen } from 'lucide-vue-next'
import { useSidebar } from '../../composables/useSidebar'

const { toggle } = useSidebar()

defineEmits(['newChat'])
</script>
```

**Step 2: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/components/layout/TopControls.vue
git commit -m "feat: 添加 TopControls 浮动控件组件"
```

---

## Task 5: 首页组件 — WelcomeHero + SuggestionCards

**Files:**
- Create: `frontend/src/components/home/WelcomeHero.vue`
- Create: `frontend/src/components/home/SuggestionCards.vue`

**Step 1: 创建 home 目录**

Run: `mkdir -p ~/Desktop/Excel/frontend/src/components/home`

**Step 2: 创建 WelcomeHero.vue**

```vue
<template>
  <div class="text-center">
    <h1 class="text-[28px] font-semibold" style="color: var(--text)">
      有什么可以帮你的？
    </h1>
  </div>
</template>
```

**Step 3: 创建 SuggestionCards.vue**

```vue
<template>
  <div class="grid grid-cols-2 gap-3 w-full max-w-[540px]">
    <button
      v-for="card in cards"
      :key="card.title"
      class="flex items-start gap-3 px-4 py-3.5 rounded-xl text-left transition-colors"
      :style="{
        background: 'var(--surface)',
        border: '1px solid var(--border)'
      }"
      @mouseenter="$event.currentTarget.style.background = 'var(--elevated)'"
      @mouseleave="$event.currentTarget.style.background = 'var(--surface)'"
      @click="$emit('select', card.prompt)"
    >
      <div
        class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
        :style="{ background: card.iconBg }"
      >
        <component :is="card.icon" class="w-4 h-4" :style="{ color: card.iconColor }" />
      </div>
      <div class="min-w-0">
        <div class="text-[14px] font-medium" style="color: var(--text)">{{ card.title }}</div>
        <div class="text-[12px] mt-0.5" style="color: var(--text-muted)">{{ card.desc }}</div>
      </div>
    </button>
  </div>
</template>

<script setup>
import { ChartBar, Sparkles, PenLine, ChartLine } from 'lucide-vue-next'

defineEmits(['select'])

const cards = [
  {
    title: '统计分析',
    desc: '计算汇总、均值、分布等统计指标',
    prompt: '帮我对这个Excel文件进行统计分析',
    icon: ChartBar,
    iconBg: 'var(--primary-muted)',
    iconColor: 'var(--primary)',
  },
  {
    title: '数据清洗',
    desc: '去重、填充空值、格式标准化',
    prompt: '帮我清洗这个Excel文件的数据',
    icon: Sparkles,
    iconBg: 'var(--success-subtle)',
    iconColor: 'var(--success-emphasis)',
  },
  {
    title: '批量修改',
    desc: '批量替换、拆分、合并单元格内容',
    prompt: '帮我批量修改这个Excel文件',
    icon: PenLine,
    iconBg: 'var(--warning-subtle)',
    iconColor: 'var(--warning-emphasis)',
  },
  {
    title: '生成图表',
    desc: '柱状图、折线图、数据可视化',
    prompt: '帮我根据这个Excel文件生成图表',
    icon: ChartLine,
    iconBg: 'var(--primary-muted)',
    iconColor: 'var(--primary)',
  },
]
</script>
```

**Step 4: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功（lucide 图标名称如 ChartBar 可能需要确认，构建时会报错则调整）

**Step 5: Commit**

```bash
git add frontend/src/components/home/
git commit -m "feat: 添加首页 WelcomeHero + SuggestionCards 组件"
```

---

## Task 6: AttachmentBar 统一附件预览

**Files:**
- Create: `frontend/src/components/common/AttachmentBar.vue`

**Step 1: 创建 common 目录**

Run: `mkdir -p ~/Desktop/Excel/frontend/src/components/common`

**Step 2: 创建 AttachmentBar.vue**

统一展示 Excel 文件标签 + 图片缩略图（从 App.vue 顶栏和 ChatInput 图片预览合并）。

```vue
<template>
  <div v-if="files.length || images.length" class="flex flex-wrap gap-2 px-3 pt-2.5">
    <!-- Excel 文件标签 -->
    <div
      v-for="f in files"
      :key="f.file_id"
      class="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-medium rounded-lg cursor-pointer transition-colors"
      :style="{
        background: 'var(--elevated)',
        border: '1px solid var(--border)',
        color: 'var(--text-secondary)'
      }"
      @click="$emit('previewFile', f)"
    >
      <FileSpreadsheet class="w-3.5 h-3.5" style="color: var(--success-emphasis)" />
      {{ f.filename }}
      <button
        @click.stop="$emit('removeFile', f.file_id)"
        class="ml-0.5 transition-colors"
        style="color: var(--text-placeholder)"
      >
        <X class="w-3 h-3" />
      </button>
    </div>

    <!-- 图片缩略图 -->
    <div
      v-for="img in images"
      :key="img.file_id"
      class="relative group w-12 h-12 rounded-lg overflow-hidden"
      :style="{ border: '1px solid var(--border)' }"
    >
      <img :src="img.previewUrl" class="w-full h-full object-cover" />
      <button
        @click="$emit('removeImage', img.file_id)"
        class="absolute -top-1 -right-1 w-5 h-5 bg-black/60 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <X class="w-3 h-3" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { FileSpreadsheet, X } from 'lucide-vue-next'

defineProps({
  files: { type: Array, default: () => [] },
  images: { type: Array, default: () => [] }
})

defineEmits(['removeFile', 'removeImage', 'previewFile'])
</script>
```

**Step 3: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 4: Commit**

```bash
git add frontend/src/components/common/AttachmentBar.vue
git commit -m "feat: 添加 AttachmentBar 统一附件预览组件"
```

---

## Task 7: ChatInput 三层重构

**Files:**
- Rewrite: `frontend/src/components/ChatInput.vue`

**Step 1: 重写 ChatInput.vue**

三层结构：AttachmentBar（附件预览）→ 文本输入 → 工具栏（📎 左侧 + 发送按钮右侧）。删除截图按钮，保留粘贴功能。

```vue
<template>
  <div class="px-4 py-3" :class="centered ? '' : 'border-t'" :style="centered ? {} : { borderColor: 'var(--border)' }">
    <div :class="centered ? 'max-w-[560px] mx-auto' : 'max-w-3xl mx-auto'">
      <div
        class="rounded-2xl transition-all"
        :style="{
          background: 'var(--surface)',
          border: '1px solid ' + (focused ? 'var(--primary)' : 'var(--input-border)'),
          boxShadow: focused ? '0 0 0 3px var(--primary-ring)' : 'none'
        }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleDrop"
      >
        <!-- 附件预览层 -->
        <AttachmentBar
          :files="files"
          :images="pendingImages"
          @removeFile="handleRemoveFile"
          @removeImage="removeImage"
          @previewFile="$emit('previewFile', $event)"
        />

        <!-- 文本输入层 -->
        <div class="flex items-end gap-2 px-4 py-3">
          <textarea
            ref="textareaRef"
            v-model="text"
            @keydown.enter.exact.prevent="handleSend"
            @paste="handlePaste"
            @input="autoResize"
            @focus="focused = true"
            @blur="focused = false"
            rows="1"
            placeholder="输入消息..."
            class="flex-1 resize-none bg-transparent text-[15px] focus:outline-none max-h-40 leading-relaxed py-0.5 placeholder:text-[var(--text-placeholder)]"
            :style="{ color: 'var(--text)' }"
          />
        </div>

        <!-- 工具栏层 -->
        <div class="flex items-center justify-between px-3 pb-2.5">
          <button
            @click="$refs.fileInput.click()"
            class="p-1 rounded-md transition-colors hover:bg-[var(--elevated)]"
            title="上传文件"
          >
            <Paperclip class="w-[18px] h-[18px]" style="color: var(--text-placeholder)" />
          </button>
          <input
            ref="fileInput"
            type="file"
            multiple
            accept=".xlsx,.xls,.csv,.png,.jpg,.jpeg,.gif,.webp"
            class="hidden"
            @change="handleFileSelect"
          />
          <button
            @click="handleSend"
            :disabled="!canSend"
            class="w-8 h-8 rounded-[10px] flex items-center justify-center transition-all"
            :style="{
              background: canSend ? 'var(--text)' : 'var(--surface-hover)',
              color: canSend ? 'var(--primary-foreground)' : 'var(--text-placeholder)',
              transform: canSend ? 'scale(1)' : 'scale(0.95)'
            }"
          >
            <ArrowUp class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- 拖拽提示 -->
      <p
        v-if="dragOver"
        class="text-xs mt-1.5 text-center font-medium"
        style="color: var(--warning-emphasis)"
      >
        松开即可上传文件
      </p>

      <!-- 上传中提示 -->
      <p
        v-if="uploading || imageUploading"
        class="text-xs mt-1.5 text-center"
        style="color: var(--text-placeholder)"
      >
        上传中...
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Paperclip, ArrowUp } from 'lucide-vue-next'
import { useFiles } from '../composables/useFiles'
import { useChat } from '../composables/useChat'
import { uploadFiles as apiUpload } from '../api'
import AttachmentBar from './common/AttachmentBar.vue'

const props = defineProps({
  centered: { type: Boolean, default: false }
})

const emit = defineEmits(['send', 'previewFile'])

const { files, uploading, upload, remove: removeFile } = useFiles()
const { streaming } = useChat()

const text = ref('')
const dragOver = ref(false)
const focused = ref(false)
const textareaRef = ref(null)
const pendingImages = ref([])
const imageUploading = ref(false)

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
const EXCEL_EXTS = ['.xlsx', '.xls', '.csv']

function isImage(filename) {
  return IMAGE_EXTS.some(ext => filename.toLowerCase().endsWith(ext))
}

const canSend = computed(() => text.value.trim() && !streaming.value)

function handleSend() {
  if (!canSend.value) return
  const imageIds = pendingImages.value.map(img => img.file_id)
  emit('send', text.value.trim(), imageIds)
  text.value = ''
  pendingImages.value.forEach(img => URL.revokeObjectURL(img.previewUrl))
  pendingImages.value = []
  if (textareaRef.value) textareaRef.value.style.height = 'auto'
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

async function uploadImages(imageFiles) {
  if (!imageFiles.length) return
  imageUploading.value = true
  try {
    const result = await apiUpload(imageFiles)
    for (let i = 0; i < result.length; i++) {
      result[i].previewUrl = URL.createObjectURL(imageFiles[i])
    }
    pendingImages.value.push(...result)
  } finally {
    imageUploading.value = false
  }
}

function removeImage(fileId) {
  const idx = pendingImages.value.findIndex(img => img.file_id === fileId)
  if (idx !== -1) {
    URL.revokeObjectURL(pendingImages.value[idx].previewUrl)
    pendingImages.value.splice(idx, 1)
  }
}

function handleRemoveFile(fileId) {
  removeFile(fileId)
}

async function handlePaste(e) {
  const items = Array.from(e.clipboardData?.items || [])
  const imageItems = items.filter(item => item.type.startsWith('image/'))
  if (!imageItems.length) return
  e.preventDefault()
  const imageFiles = imageItems
    .map(item => item.getAsFile())
    .filter(Boolean)
    .map((file, i) => {
      const ext = file.type.split('/')[1] || 'png'
      return new File([file], `screenshot_${Date.now()}_${i}.${ext}`, { type: file.type })
    })
  await uploadImages(imageFiles)
}

async function handleDrop(e) {
  dragOver.value = false
  const allFiles = Array.from(e.dataTransfer.files)
  const excelFiles = allFiles.filter(f => EXCEL_EXTS.some(ext => f.name.toLowerCase().endsWith(ext)))
  const imageFiles = allFiles.filter(f => isImage(f.name))
  if (excelFiles.length) await upload(excelFiles)
  if (imageFiles.length) await uploadImages(imageFiles)
}

async function handleFileSelect(e) {
  const allFiles = Array.from(e.target.files)
  const excelFiles = allFiles.filter(f => EXCEL_EXTS.some(ext => f.name.toLowerCase().endsWith(ext)))
  const imageFiles = allFiles.filter(f => isImage(f.name))
  if (excelFiles.length) await upload(excelFiles)
  if (imageFiles.length) await uploadImages(imageFiles)
  e.target.value = ''
}
</script>
```

**Step 2: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/components/ChatInput.vue
git commit -m "refactor: ChatInput 三层结构重构（附件预览+文本+工具栏）"
```

---

## Task 8: MessageList 提取

**Files:**
- Create: `frontend/src/components/chat/MessageList.vue`

**Step 1: 创建 chat 目录**

Run: `mkdir -p ~/Desktop/Excel/frontend/src/components/chat`

**Step 2: 创建 MessageList.vue**

从 ChatPanel 提取消息列表滚动区域和状态指示器。

```vue
<template>
  <div ref="scrollContainer" class="flex-1 overflow-y-auto" @scroll="handleScroll">
    <div class="max-w-3xl mx-auto py-8 px-4">
      <MessageBubble
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- 状态指示器 -->
      <div
        v-if="status"
        class="flex items-center gap-2 text-[13px] mb-6 pl-0.5"
        style="color: var(--text-placeholder)"
      >
        <div class="flex gap-1" v-if="status === 'thinking'">
          <span class="w-1.5 h-1.5 rounded-full animate-bounce" style="background: var(--text-placeholder); animation-delay: 0ms" />
          <span class="w-1.5 h-1.5 rounded-full animate-bounce" style="background: var(--text-placeholder); animation-delay: 150ms" />
          <span class="w-1.5 h-1.5 rounded-full animate-bounce" style="background: var(--text-placeholder); animation-delay: 300ms" />
        </div>
        <svg v-else class="w-4 h-4 animate-spin" style="color: var(--text-placeholder)" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25" />
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <span class="text-xs">{{ statusLabel }}</span>
        <span v-if="elapsed > 0" class="text-xs" style="color: var(--border-strong)">{{ elapsed }}s</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed, onUnmounted } from 'vue'
import MessageBubble from '../MessageBubble.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  status: { type: String, default: null }
})

const scrollContainer = ref(null)
const userScrolledUp = ref(false)
const elapsed = ref(0)
let timerInterval = null
let timerStart = 0

const statusLabel = computed(() => {
  switch (props.status) {
    case 'thinking': return '分析中'
    case 'running': return '执行代码中'
    case 'verifying': return '验证结果中'
    case 'reporting': return '生成报告中'
    default: return ''
  }
})

watch(() => props.status, (val) => {
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

function handleScroll() {
  const el = scrollContainer.value
  if (!el) return
  userScrolledUp.value = el.scrollHeight - el.scrollTop - el.clientHeight > 100
}

watch(
  () => {
    const last = props.messages[props.messages.length - 1]
    return last?.content?.length || last?.toolCalls?.length || props.messages.length
  },
  async () => {
    if (userScrolledUp.value) return
    await nextTick()
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  }
)
</script>
```

**Step 3: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 4: Commit**

```bash
git add frontend/src/components/chat/MessageList.vue
git commit -m "feat: 提取 MessageList 组件（消息列表+状态指示器）"
```

---

## Task 9: ChatPanel 双模式重构

**Files:**
- Rewrite: `frontend/src/components/ChatPanel.vue`

**Step 1: 重写 ChatPanel.vue**

根据 `hasMessages` 在首页模式和对话模式间切换。

```vue
<template>
  <div class="flex-1 flex flex-col min-h-0 relative">
    <!-- 浮动控件 -->
    <TopControls @newChat="$emit('newChat')" />

    <!-- 首页模式：无消息时 -->
    <template v-if="!hasMessages">
      <div class="flex-1 flex flex-col items-center justify-center gap-6 px-4">
        <WelcomeHero />
        <SuggestionCards @select="handleSuggestion" />
        <ChatInput centered @send="handleSend" @previewFile="$emit('previewFile', $event)" />
      </div>
    </template>

    <!-- 对话模式：有消息时 -->
    <template v-else>
      <MessageList :messages="messages" :status="status" />
      <ChatInput @send="handleSend" @previewFile="$emit('previewFile', $event)" />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useChat } from '../composables/useChat'
import { useFiles } from '../composables/useFiles'
import { useConversations } from '../composables/useConversations'
import TopControls from './layout/TopControls.vue'
import WelcomeHero from './home/WelcomeHero.vue'
import SuggestionCards from './home/SuggestionCards.vue'
import MessageList from './chat/MessageList.vue'
import ChatInput from './ChatInput.vue'

const emit = defineEmits(['newChat', 'previewFile'])

const { messages, status, send } = useChat()
const { files } = useFiles()
const { currentConvId, create } = useConversations()

const hasMessages = computed(() => messages.value.length > 0)

async function handleSend(text, imageIds = []) {
  const fileIds = files.value.map(f => f.file_id)
  let convId = currentConvId.value
  if (!convId) {
    convId = await create()
  }
  send(text, fileIds, convId, imageIds)
}

function handleSuggestion(prompt) {
  handleSend(prompt)
}
</script>
```

**Step 2: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/components/ChatPanel.vue
git commit -m "refactor: ChatPanel 双模式重构（首页/对话切换）"
```

---

## Task 10: SettingsPage 独立设置页

**Files:**
- Create: `frontend/src/components/SettingsPage.vue`

**Step 1: 创建 SettingsPage.vue**

从 SettingsModal.vue 提取逻辑，改为独立页面布局（非弹窗）。保持全部业务逻辑不变，只改 UI 结构。

将原 SettingsModal.vue 的 `<script setup>` 完整保留（189-271 行），模板改为页面布局：

```vue
<template>
  <div class="flex-1 flex flex-col min-h-0 relative">
    <!-- 浮动控件 -->
    <TopControls @newChat="$emit('newChat')" />

    <div class="flex-1 overflow-y-auto">
      <div class="max-w-xl px-6 py-14 mx-auto space-y-8">
        <!-- 页面标题 -->
        <div>
          <h1 class="text-2xl font-semibold" style="color: var(--text)">设置</h1>
          <p class="text-[14px] mt-1" style="color: var(--text-muted)">
            管理 AI 模型配置、用户账号和安全设置
          </p>
        </div>

        <div class="h-px" style="background: var(--border)" />

        <!-- AI 模型设置 -->
        <section class="space-y-5">
          <div class="flex items-center gap-2">
            <Bot class="w-[18px] h-[18px]" style="color: var(--primary)" />
            <h2 class="text-base font-semibold" style="color: var(--text)">AI 模型</h2>
          </div>
          <div class="space-y-4 max-w-md">
            <div>
              <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">服务商</label>
              <select
                v-model="provider"
                @change="onProviderChange"
                class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none bg-[var(--surface)]"
                :style="{ border: '1px solid var(--input-border)', color: 'var(--text)' }"
              >
                <option value="deepseek">DeepSeek</option>
                <option value="aliyun">阿里云（通义千问）</option>
              </select>
            </div>
            <div>
              <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">API Key</label>
              <div class="flex gap-2">
                <input
                  v-model="apiKey"
                  :type="showKey ? 'text' : 'password'"
                  :placeholder="apiKeyMasked || '请输入 API Key'"
                  class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
                  :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
                />
                <button
                  @click="showKey = !showKey"
                  class="px-2.5 rounded-lg transition-colors"
                  :style="{ border: '1px solid var(--border)', color: 'var(--text-muted)' }"
                >
                  <component :is="showKey ? EyeOff : Eye" class="w-4 h-4" />
                </button>
              </div>
            </div>
            <div>
              <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">Base URL</label>
              <input
                v-model="baseUrl"
                :placeholder="currentProviderBaseUrl"
                class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
                :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
              />
            </div>
            <div>
              <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">模型</label>
              <select
                v-model="model"
                class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none bg-[var(--surface)]"
                :style="{ border: '1px solid var(--input-border)', color: 'var(--text)' }"
              >
                <option v-for="m in currentModelList" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>
            <div class="flex items-center gap-3">
              <button
                @click="saveSettings"
                :disabled="saving"
                class="px-5 py-2.5 text-[14px] font-medium rounded-[10px] text-white disabled:opacity-50 transition-colors"
                style="background: var(--primary)"
              >
                {{ saving ? '保存中...' : '保存' }}
              </button>
              <span v-if="saveSuccess" class="text-[13px]" style="color: var(--success-emphasis)">已保存</span>
            </div>
          </div>
        </section>

        <div class="h-px" style="background: var(--border)" />

        <!-- 用户管理（仅管理员） -->
        <section v-if="isAdmin" class="space-y-5">
          <div class="flex items-center gap-2">
            <Users class="w-[18px] h-[18px]" style="color: var(--primary)" />
            <h2 class="text-base font-semibold" style="color: var(--text)">用户管理</h2>
            <span
              class="text-[11px] font-medium px-2 py-0.5 rounded"
              :style="{ background: 'var(--primary-muted)', color: 'var(--primary)' }"
            >仅管理员</span>
          </div>
          <div class="space-y-1 max-w-md">
            <div
              v-for="u in userList"
              :key="u.id"
              class="flex items-center gap-2 px-3.5 py-2.5 rounded-lg text-[14px]"
              style="background: var(--background)"
            >
              <span class="flex-1" style="color: var(--text)">{{ u.username }}</span>
              <span
                v-if="u.is_admin"
                class="text-[11px] font-medium px-2 py-0.5 rounded"
                :style="{ background: 'var(--warning-subtle)', color: 'var(--warning-emphasis)' }"
              >管理员</span>
              <button
                v-if="u.id !== currentUser?.id"
                @click="handleDeleteUser(u.id)"
                style="color: var(--text-placeholder)"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          <div class="flex gap-2 max-w-md">
            <input
              v-model="newUsername"
              placeholder="用户名"
              class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
              :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
            />
            <input
              v-model="newPassword"
              type="password"
              placeholder="密码"
              class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
              :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
            />
            <button
              @click="handleAddUser"
              :disabled="!newUsername || !newPassword"
              class="px-4 py-2.5 text-[14px] font-medium text-white rounded-lg disabled:opacity-50 transition-colors"
              style="background: var(--text)"
            >
              添加
            </button>
          </div>
          <div v-if="userError" class="text-[13px]" style="color: var(--error-emphasis)">{{ userError }}</div>
        </section>

        <div v-if="isAdmin" class="h-px" style="background: var(--border)" />

        <!-- 修改密码 -->
        <section class="space-y-5">
          <div class="flex items-center gap-2">
            <Lock class="w-[18px] h-[18px]" style="color: var(--primary)" />
            <h2 class="text-base font-semibold" style="color: var(--text)">修改密码</h2>
          </div>
          <div class="space-y-4 max-w-md">
            <div>
              <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">当前密码</label>
              <input
                v-model="oldPw"
                type="password"
                placeholder="输入当前密码"
                class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
                :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
              />
            </div>
            <div>
              <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">新密码</label>
              <input
                v-model="newPw"
                type="password"
                placeholder="输入新密码"
                class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
                :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
              />
            </div>
            <div class="flex items-center gap-3">
              <button
                @click="handleChangePassword"
                :disabled="!oldPw || !newPw"
                class="px-5 py-2.5 text-[14px] font-medium text-white rounded-[10px] disabled:opacity-50 transition-colors"
                style="background: var(--text)"
              >
                修改密码
              </button>
              <span v-if="pwSuccess" class="text-[13px]" style="color: var(--success-emphasis)">修改成功</span>
              <span v-if="pwError" class="text-[13px]" style="color: var(--error-emphasis)">{{ pwError }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Bot, Users, Trash2, Eye, EyeOff, Lock } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'
import TopControls from './layout/TopControls.vue'
import {
  getSettings, updateSettings,
  listUsers, createUser, deleteUser, changePassword
} from '../api'

defineEmits(['newChat'])

const { user: currentUser, isAdmin } = useAuth()

const provider = ref('deepseek')
const providers = ref({})
const apiKey = ref('')
const apiKeyMasked = ref('')
const baseUrl = ref('')
const model = ref('')
const showKey = ref(false)
const saving = ref(false)
const saveSuccess = ref(false)

const currentModelList = computed(() => providers.value[provider.value]?.models || [])
const currentProviderBaseUrl = computed(() => providers.value[provider.value]?.default_base_url || '')

function onProviderChange() {
  const cfg = providers.value[provider.value]
  if (cfg) {
    baseUrl.value = cfg.default_base_url
    model.value = cfg.models[0] || ''
  }
  apiKey.value = ''
  apiKeyMasked.value = ''
}

const userList = ref([])
const newUsername = ref('')
const newPassword = ref('')
const userError = ref('')

const oldPw = ref('')
const newPw = ref('')
const pwSuccess = ref(false)
const pwError = ref('')

async function loadSettings() {
  try {
    const data = await getSettings()
    provider.value = data.provider || 'deepseek'
    providers.value = data.providers || {}
    apiKeyMasked.value = data.api_key_masked
    baseUrl.value = data.base_url
    model.value = data.model
  } catch {}
}

async function saveSettings() {
  saving.value = true
  saveSuccess.value = false
  try {
    const updates = { provider: provider.value, base_url: baseUrl.value, model: model.value }
    if (apiKey.value) updates.api_key = apiKey.value
    await updateSettings(updates)
    saveSuccess.value = true
    apiKey.value = ''
    await loadSettings()
    setTimeout(() => saveSuccess.value = false, 2000)
  } finally {
    saving.value = false
  }
}

async function loadUsers() {
  if (!isAdmin.value) return
  try { userList.value = await listUsers() } catch {}
}

async function handleAddUser() {
  userError.value = ''
  try {
    await createUser(newUsername.value, newPassword.value, false)
    newUsername.value = ''
    newPassword.value = ''
    await loadUsers()
  } catch (e) {
    userError.value = e.response?.data?.detail || '添加失败'
  }
}

async function handleDeleteUser(userId) {
  await deleteUser(userId)
  await loadUsers()
}

async function handleChangePassword() {
  pwError.value = ''
  pwSuccess.value = false
  try {
    await changePassword(oldPw.value, newPw.value)
    oldPw.value = ''
    newPw.value = ''
    pwSuccess.value = true
    setTimeout(() => pwSuccess.value = false, 2000)
  } catch (e) {
    pwError.value = e.response?.data?.detail || '修改失败'
  }
}

onMounted(() => {
  loadSettings()
  loadUsers()
})
</script>
```

注意：这个组件超过 150 行模板，但设置页本身有三个独立区块，后续可进一步拆分为 `AiModelSettings`、`UserManagement`、`ChangePassword` 三个子组件。首轮重构先做到页面级可用。

**Step 2: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/components/SettingsPage.vue
git commit -m "feat: 添加 SettingsPage 独立设置页面（替代弹窗）"
```

---

## Task 11: App.vue 重写 — 组装全部组件

**Files:**
- Rewrite: `frontend/src/components/App.vue` → 实际是 `frontend/src/App.vue`

**Step 1: 重写 App.vue**

删除旧的顶栏 header，用 `currentView` 状态切换聊天/设置视图。

```vue
<template>
  <!-- 未登录 -->
  <LoginPage v-if="!isLoggedIn" />

  <!-- 已登录 -->
  <div v-else class="h-screen flex" style="background: var(--background)">
    <!-- 侧边栏 -->
    <Sidebar
      @openSettings="currentView = 'settings'"
      @selectConversation="handleSelectConversation"
    />

    <!-- 主区域 -->
    <ChatPanel
      v-if="currentView === 'chat'"
      @newChat="handleNewChat"
      @previewFile="openPreview"
    />
    <SettingsPage
      v-else-if="currentView === 'settings'"
      @newChat="handleNewChat"
    />

    <!-- Excel 预览弹窗 -->
    <ExcelPreview
      v-if="previewFile"
      :file-id="previewFile.file_id"
      :filename="previewFile.filename"
      @close="previewFile = null"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuth } from './composables/useAuth'
import { useFiles } from './composables/useFiles'
import { useChat } from './composables/useChat'
import { useConversations } from './composables/useConversations'
import LoginPage from './components/LoginPage.vue'
import Sidebar from './components/Sidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import SettingsPage from './components/SettingsPage.vue'
import ExcelPreview from './components/ExcelPreview.vue'

const { isLoggedIn } = useAuth()
const { clear: clearFiles } = useFiles()
const { clearMessages, loadFromHistory } = useChat()
const { create, select, currentConvId, loadMessages } = useConversations()

const currentView = ref('chat')
const previewFile = ref(null)

function openPreview(file) {
  previewFile.value = file
}

async function handleNewChat() {
  currentView.value = 'chat'
  clearMessages()
  clearFiles()
  const convId = await create()
  select(convId)
}

async function handleSelectConversation(convId) {
  currentView.value = 'chat'
  clearMessages()
  clearFiles()
  select(convId)
  const data = await loadMessages(convId)
  if (data.messages) {
    loadFromHistory(data.messages)
  }
}
</script>
```

**Step 2: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/App.vue
git commit -m "refactor: App.vue 重写 — 组装新组件、删除旧顶栏、切换聊天/设置视图"
```

---

## Task 12: 清理旧文件

**Files:**
- Delete: `frontend/src/components/ScreenCapture.vue`
- Delete: `frontend/src/components/SettingsModal.vue`

**Step 1: 确认无引用**

搜索 `ScreenCapture` 和 `SettingsModal` 在代码中的引用，确认 App.vue 已不再导入它们。

Run: `cd ~/Desktop/Excel/frontend && grep -r "ScreenCapture\|SettingsModal" src/ --include="*.vue" --include="*.js"`
Expected: 无匹配结果（如果有残留引用需先修复）

**Step 2: 删除文件**

Run: `rm ~/Desktop/Excel/frontend/src/components/ScreenCapture.vue ~/Desktop/Excel/frontend/src/components/SettingsModal.vue`

**Step 3: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 4: Commit**

```bash
git add frontend/src/components/ScreenCapture.vue frontend/src/components/SettingsModal.vue
git commit -m "chore: 删除 ScreenCapture 和 SettingsModal 旧组件"
```

---

## Task 13: 全局辅助样式

**Files:**
- Modify: `frontend/src/styles/main.css`

**Step 1: 添加 textarea placeholder 和 select 样式**

在 main.css 末尾追加（侧边栏动画已通过内联 style + transition-all 实现，无需额外 CSS）：

```css
/* textarea / select 统一样式 */
select {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239CA3AF' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}
```

**Step 2: 验证构建**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功

**Step 3: Commit**

```bash
git add frontend/src/styles/main.css
git commit -m "feat: 添加侧边栏收起/展开过渡动画"
```

---

## Task 14: 端到端验收

**Step 1: 启动开发服务器**

Run: `cd ~/Desktop/Excel/frontend && npm run dev`

**Step 2: 浏览器验收清单**

逐项在浏览器中验证：

- [ ] 登录页正常显示
- [ ] 登录后进入首页模式（欢迎语 + 建议卡片 + 居中输入框）
- [ ] 侧边栏显示对话列表
- [ ] 点击侧边栏收起按钮，侧边栏平滑隐藏
- [ ] 再次点击展开
- [ ] 在首页输入消息并发送，切换到对话模式
- [ ] 对话模式消息正常显示（用户气泡 + AI 回复 + 工具调用折叠）
- [ ] 输入框三层结构：附件预览 + 文本 + 工具栏
- [ ] 拖拽文件到输入框，附件标签显示在输入框内
- [ ] Ctrl+V 粘贴图片，图片缩略图显示在附件区域
- [ ] 点击侧边栏设置图标，进入设置页面
- [ ] 设置页 AI 模型配置正常
- [ ] 设置页用户管理正常（管理员账号）
- [ ] 设置页修改密码正常
- [ ] 点击新对话按钮从设置页返回聊天
- [ ] 品牌色 #3B63C9 正确应用（Logo、建议卡片图标、设置页按钮等）

**Step 3: 修复验收中发现的问题**

逐个修复，每个修复单独 commit。

**Step 4: 最终构建验证**

Run: `cd ~/Desktop/Excel/frontend && npm run build`
Expected: 构建成功，无错误

---

## 文件变更总览

### 新增文件（9 个）
| 文件 | 行数估算 |
|------|---------|
| `composables/useSidebar.js` | ~20 |
| `components/layout/SidebarHeader.vue` | ~30 |
| `components/layout/ConversationList.vue` | ~70 |
| `components/layout/SidebarFooter.vue` | ~35 |
| `components/layout/TopControls.vue` | ~25 |
| `components/home/WelcomeHero.vue` | ~8 |
| `components/home/SuggestionCards.vue` | ~60 |
| `components/chat/MessageList.vue` | ~85 |
| `components/common/AttachmentBar.vue` | ~50 |

### 重写文件（4 个）
| 文件 | 原行数 → 新行数估算 |
|------|-------------------|
| `App.vue` | 98 → ~60 |
| `Sidebar.vue` | 124 → ~45 |
| `ChatPanel.vue` | 131 → ~50 |
| `ChatInput.vue` | 244 → ~130 |

### 新增页面（1 个）
| 文件 | 行数估算 |
|------|---------|
| `SettingsPage.vue` | ~200（后续可拆分） |

### 删除文件（2 个）
- `ScreenCapture.vue`（244 行）
- `SettingsModal.vue`（271 行）

### 修改文件（1 个）
- `styles/main.css`（添加 CSS 变量 + 动画）

<template>
  <div class="border-t border-[#e5e5e5] bg-white px-4 py-3">
    <div class="max-w-3xl mx-auto">
      <div
        class="border border-[#d9d9d9] rounded-2xl px-3 py-2 focus-within:border-[#999] focus-within:shadow-sm transition-all bg-white"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleDrop"
        :class="{ 'border-orange-400 bg-orange-50/30': dragOver }"
      >
        <!-- 图片预览区 -->
        <div v-if="pendingImages.length" class="flex flex-wrap gap-2 mb-2 pt-1">
          <div
            v-for="img in pendingImages"
            :key="img.file_id"
            class="relative group w-16 h-16 rounded-lg overflow-hidden border border-[#e5e5e5]"
          >
            <img :src="img.previewUrl" class="w-full h-full object-cover" />
            <button
              @click="removeImage(img.file_id)"
              class="absolute -top-1 -right-1 w-5 h-5 bg-black/60 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <X class="w-3 h-3" />
            </button>
          </div>
        </div>

        <div class="flex items-end gap-2">
          <!-- 上传按钮 -->
          <button
            @click="$refs.fileInput.click()"
            class="p-1.5 text-[#999] hover:text-[#555] rounded-lg hover:bg-[#f4f4f4] transition-colors shrink-0 mb-0.5"
            title="上传文件（Excel / 图片）"
          >
            <Paperclip class="w-5 h-5" />
          </button>
          <input
            ref="fileInput"
            type="file"
            multiple
            accept=".xlsx,.xls,.csv,.png,.jpg,.jpeg,.gif,.webp"
            class="hidden"
            @change="handleFileSelect"
          />

          <!-- 粘贴截图按钮 -->
          <button
            @click="pasteFromClipboard"
            class="p-1.5 text-[#999] hover:text-[#555] rounded-lg hover:bg-[#f4f4f4] transition-colors shrink-0 mb-0.5"
            title="粘贴剪贴板截图 (Alt+S)"
          >
            <Scissors class="w-5 h-5" />
          </button>

          <!-- 文本输入 -->
          <textarea
            ref="textareaRef"
            v-model="text"
            @keydown.enter.exact.prevent="handleSend"
            @paste="handlePaste"
            @input="autoResize"
            rows="1"
            placeholder="输入消息...  Ctrl+V 粘贴截图 / Alt+S 从剪贴板读取"
            class="flex-1 resize-none bg-transparent text-[15px] text-[#1a1a1a] placeholder-[#999] focus:outline-none max-h-40 leading-relaxed py-1"
          />

          <!-- 发送按钮 -->
          <button
            @click="handleSend"
            :disabled="!canSend"
            :class="[
              'p-2 rounded-xl transition-all shrink-0 mb-0.5',
              canSend
                ? 'bg-[#1a1a1a] text-white hover:bg-[#333] scale-100'
                : 'bg-[#e5e5e5] text-[#999] scale-95'
            ]"
          >
            <ArrowUp class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- 拖拽提示 -->
      <p v-if="dragOver" class="text-xs text-orange-500 mt-1.5 text-center font-medium">
        松开即可上传文件
      </p>

      <!-- 上传中提示 -->
      <p v-if="uploading || imageUploading" class="text-xs text-[#999] mt-1.5 text-center">
        上传中...
      </p>

      <!-- 剪贴板提示 -->
      <p v-if="clipboardHint" class="text-xs text-orange-500 mt-1.5 text-center">
        {{ clipboardHint }}
      </p>
    </div>
  </div>

</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Paperclip, ArrowUp, X, Scissors } from 'lucide-vue-next'
import { useFiles } from '../composables/useFiles'
import { useChat } from '../composables/useChat'
import { uploadFiles as apiUpload } from '../api'

const emit = defineEmits(['send'])

const { files, uploading, upload } = useFiles()
const { streaming } = useChat()

const text = ref('')
const dragOver = ref(false)
const textareaRef = ref(null)
const pendingImages = ref([])
const imageUploading = ref(false)
const clipboardHint = ref('')

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.webp']
const EXCEL_EXTS = ['.xlsx', '.xls', '.csv']

function isImage(filename) {
  return IMAGE_EXTS.some(ext => filename.toLowerCase().endsWith(ext))
}

const canSend = computed(
  () => text.value.trim() && !streaming.value
)

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

// 从剪贴板读取截图
async function pasteFromClipboard() {
  try {
    const items = await navigator.clipboard.read()
    const imageFiles = []
    for (const item of items) {
      const imageType = item.types.find(t => t.startsWith('image/'))
      if (imageType) {
        const blob = await item.getType(imageType)
        imageFiles.push(new File([blob], `screenshot_${Date.now()}.png`, { type: 'image/png' }))
      }
    }
    if (imageFiles.length) {
      await uploadImages(imageFiles)
    } else {
      showHint('剪贴板无图片，请先截图 (⌘⇧4 / Win+Shift+S)')
    }
  } catch {
    showHint('剪贴板无图片，请先截图 (⌘⇧4 / Win+Shift+S)')
  }
}

function showHint(msg) {
  clipboardHint.value = msg
  setTimeout(() => { clipboardHint.value = '' }, 3000)
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

// Alt+S 全局快捷键
function handleGlobalKeydown(e) {
  if (e.altKey && e.key.toLowerCase() === 's') {
    e.preventDefault()
    pasteFromClipboard()
  }
}

onMounted(() => document.addEventListener('keydown', handleGlobalKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleGlobalKeydown))
</script>

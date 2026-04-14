<template>
  <div :class="centered ? 'w-full px-4 py-3' : 'px-4 py-3 border-t'" :style="centered ? {} : { borderColor: 'var(--border)' }">
    <div :class="centered ? 'w-full max-w-[540px] mx-auto' : 'max-w-4xl mx-auto'">
      <div
        class="rounded-2xl transition-all"
        :style="{
          background: 'var(--surface)',
          border: '1px solid ' + (focused ? 'var(--primary)' : 'var(--input-border)'),
          boxShadow: focused ? '0 0 0 3px var(--primary-ring)' : 'none'
        }"
        @dragenter.prevent="dragCounter++"
        @dragleave="dragCounter--"
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
            class="p-1 rounded-md transition-colors"
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

      <p v-if="dragOver" class="text-xs mt-1.5 text-center font-medium" style="color: var(--warning-emphasis)">
        松开即可上传文件
      </p>
      <p v-if="uploading || imageUploading" class="text-xs mt-1.5 text-center" style="color: var(--text-placeholder)">
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

defineProps({
  centered: { type: Boolean, default: false }
})

const emit = defineEmits(['send', 'previewFile'])

const { files, uploading, upload, remove: removeFile } = useFiles()
const { streaming } = useChat()

const text = ref('')
const dragCounter = ref(0)
const dragOver = computed(() => dragCounter.value > 0)
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
  dragCounter.value = 0
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

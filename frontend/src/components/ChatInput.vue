<template>
  <div class="border-t border-[#e5e5e5] bg-white px-4 py-3">
    <div class="max-w-3xl mx-auto">
      <div
        class="flex items-end gap-2 border border-[#d9d9d9] rounded-2xl px-3 py-2 focus-within:border-[#999] focus-within:shadow-sm transition-all bg-white"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleDrop"
        :class="{ 'border-orange-400 bg-orange-50/30': dragOver }"
      >
        <!-- 上传按钮 -->
        <button
          @click="$refs.fileInput.click()"
          class="p-1.5 text-[#999] hover:text-[#555] rounded-lg hover:bg-[#f4f4f4] transition-colors shrink-0 mb-0.5"
          title="上传 Excel 文件"
        >
          <Paperclip class="w-5 h-5" />
        </button>
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".xlsx,.xls,.csv"
          class="hidden"
          @change="handleFileSelect"
        />

        <!-- 文本输入 -->
        <textarea
          ref="textareaRef"
          v-model="text"
          @keydown.enter.exact.prevent="handleSend"
          @input="autoResize"
          rows="1"
          placeholder="描述你想对 Excel 做什么..."
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

      <!-- 拖拽提示 -->
      <p v-if="dragOver" class="text-xs text-orange-500 mt-1.5 text-center font-medium">
        松开即可上传文件
      </p>

      <!-- 上传中提示 -->
      <p v-if="uploading" class="text-xs text-[#999] mt-1.5 text-center">
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

const emit = defineEmits(['send'])

const { files, uploading, upload } = useFiles()
const { streaming } = useChat()

const text = ref('')
const dragOver = ref(false)
const textareaRef = ref(null)

const canSend = computed(
  () => text.value.trim() && files.value.length > 0 && !streaming.value
)

function handleSend() {
  if (!canSend.value) return
  emit('send', text.value.trim())
  text.value = ''
  if (textareaRef.value) textareaRef.value.style.height = 'auto'
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

async function handleDrop(e) {
  dragOver.value = false
  const droppedFiles = Array.from(e.dataTransfer.files).filter(
    f => f.name.endsWith('.xlsx') || f.name.endsWith('.xls') || f.name.endsWith('.csv')
  )
  if (droppedFiles.length) await upload(droppedFiles)
}

async function handleFileSelect(e) {
  const selected = Array.from(e.target.files)
  if (selected.length) await upload(selected)
  e.target.value = ''
}
</script>

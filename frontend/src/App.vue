<template>
  <div class="h-screen flex flex-col bg-white">
    <!-- 顶栏 -->
    <header class="h-13 border-b border-[#e5e5e5] flex items-center px-5 shrink-0">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-lg bg-[#1a1a1a] flex items-center justify-center">
          <FileSpreadsheet class="w-4 h-4 text-white" />
        </div>
        <h1 class="text-[15px] font-semibold text-[#1a1a1a]">Excel Agent</h1>
      </div>

      <!-- 已上传文件标签 -->
      <div class="ml-6 flex items-center gap-2 overflow-x-auto">
        <span
          v-for="f in files"
          :key="f.file_id"
          class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-[#f4f4f4] text-[#555] text-xs font-medium rounded-lg border border-[#e5e5e5] shrink-0"
        >
          <FileSpreadsheet class="w-3 h-3 text-green-600" />
          {{ f.filename }}
          <button
            @click="remove(f.file_id)"
            class="ml-0.5 text-[#999] hover:text-[#333] transition-colors"
          >
            <X class="w-3 h-3" />
          </button>
        </span>
      </div>

      <!-- 清除对话 -->
      <button
        v-if="messages.length > 0"
        @click="handleClear"
        class="ml-auto text-xs text-[#999] hover:text-[#555] transition-colors px-2 py-1 rounded-md hover:bg-[#f4f4f4]"
      >
        新对话
      </button>
    </header>

    <!-- 聊天区 -->
    <ChatPanel />
  </div>
</template>

<script setup>
import { FileSpreadsheet, X } from 'lucide-vue-next'
import { useFiles } from './composables/useFiles'
import { useChat } from './composables/useChat'
import ChatPanel from './components/ChatPanel.vue'

const { files, remove, clear: clearFiles } = useFiles()
const { messages, clearMessages } = useChat()

function handleClear() {
  clearMessages()
  clearFiles()
}
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0">
    <!-- 消息列表 -->
    <div ref="scrollContainer" class="flex-1 overflow-y-auto">
      <div class="max-w-3xl mx-auto py-8 px-4">
        <!-- 空状态 -->
        <div
          v-if="messages.length === 0"
          class="flex flex-col items-center justify-center pt-32 text-center"
        >
          <div class="w-14 h-14 rounded-2xl bg-[#f4f4f4] flex items-center justify-center mb-4">
            <FileSpreadsheet class="w-7 h-7 text-[#999]" />
          </div>
          <p class="text-lg font-semibold text-[#1a1a1a] mb-1">Excel Agent</p>
          <p class="text-sm text-[#999] max-w-sm">
            上传 Excel 文件，用自然语言描述你想做的操作。支持数据清洗、统计分析、批量修改等。
          </p>
        </div>

        <!-- 消息列表 -->
        <MessageBubble
          v-for="(msg, i) in messages"
          :key="i"
          :message="msg"
        />

        <!-- 流式加载指示器 -->
        <div v-if="streaming && messages.length > 0" class="flex items-center gap-2 text-[#999] text-sm mb-6">
          <div class="flex gap-1">
            <span class="w-1.5 h-1.5 bg-[#999] rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-1.5 h-1.5 bg-[#999] rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 bg-[#999] rounded-full animate-bounce" style="animation-delay: 300ms" />
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <ChatInput @send="handleSend" />
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { FileSpreadsheet } from 'lucide-vue-next'
import { useChat } from '../composables/useChat'
import { useFiles } from '../composables/useFiles'
import MessageBubble from './MessageBubble.vue'
import ChatInput from './ChatInput.vue'

const { messages, streaming, send } = useChat()
const { files } = useFiles()
const scrollContainer = ref(null)

function handleSend(text) {
  const fileIds = files.value.map(f => f.file_id)
  send(text, fileIds)
}

// 自动滚动到底部
watch(
  () => {
    const last = messages.value[messages.value.length - 1]
    return last?.content?.length || last?.toolCalls?.length || messages.value.length
  },
  async () => {
    await nextTick()
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  }
)
</script>

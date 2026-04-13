<template>
  <div class="flex-1 flex flex-col min-h-0">
    <!-- 消息列表 -->
    <div ref="scrollContainer" class="flex-1 overflow-y-auto" @scroll="handleScroll">
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
          v-for="msg in messages"
          :key="msg.id"
          :message="msg"
        />

        <!-- 流式加载指示器 -->
        <div v-if="streaming && messages.length > 0 && !lastMessageHasContent" class="flex items-center gap-2 text-[#999] text-sm mb-6">
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
import { ref, watch, nextTick, computed } from 'vue'
import { FileSpreadsheet } from 'lucide-vue-next'
import { useChat } from '../composables/useChat'
import { useFiles } from '../composables/useFiles'
import { useConversations } from '../composables/useConversations'
import MessageBubble from './MessageBubble.vue'
import ChatInput from './ChatInput.vue'

const { messages, streaming, send } = useChat()
const { files } = useFiles()
const { currentConvId, create } = useConversations()
const scrollContainer = ref(null)
const userScrolledUp = ref(false)

const lastMessageHasContent = computed(() => {
  const last = messages.value[messages.value.length - 1]
  return last && (last.content || last.toolCalls?.length > 0)
})

async function handleSend(text) {
  const fileIds = files.value.map(f => f.file_id)
  // 如果没有当前对话，自动创建一个
  let convId = currentConvId.value
  if (!convId) {
    convId = await create()
  }
  send(text, fileIds, convId)
}

function handleScroll() {
  const el = scrollContainer.value
  if (!el) return
  const threshold = 100
  userScrolledUp.value = el.scrollHeight - el.scrollTop - el.clientHeight > threshold
}

// 自动滚动到底部（仅当用户没有上滑时）
watch(
  () => {
    const last = messages.value[messages.value.length - 1]
    return last?.content?.length || last?.toolCalls?.length || messages.value.length
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

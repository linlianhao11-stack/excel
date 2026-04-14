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
const { currentConvId, create, load: reloadConversations } = useConversations()

const hasMessages = computed(() => messages.value.length > 0)

async function handleSend(text, imageIds = []) {
  const fileIds = files.value.map(f => f.file_id)
  let convId = currentConvId.value
  if (!convId) {
    convId = await create()
    reloadConversations()
  }
  send(text, fileIds, convId, imageIds)
}

function handleSuggestion(prompt) {
  handleSend(prompt)
}
</script>

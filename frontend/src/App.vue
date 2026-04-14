<template>
  <!-- 未登录 -->
  <LoginPage v-if="!isLoggedIn" />

  <!-- 已登录 -->
  <div v-else class="h-screen flex" style="background: var(--background)">
    <!-- 侧边栏 -->
    <Sidebar
      @openSettings="currentView = 'settings'"
      @selectConversation="handleSelectConversation"
      @newChat="handleNewChat"
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
import { ref, onMounted } from 'vue'
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
const { create, select, loadMessages, load: reloadConversations } = useConversations()

const currentView = ref('chat')
const previewFile = ref(null)

// 刷新时恢复上次的对话
onMounted(async () => {
  if (isLoggedIn.value) {
    await reloadConversations()
    const { currentConvId } = useConversations()
    if (currentConvId.value) {
      try {
        const data = await loadMessages(currentConvId.value)
        if (data.messages) {
          loadFromHistory(data.messages)
        }
      } catch {
        // 对话已不存在，清理
        select(null)
        clearMessages()
      }
    }
  }
})

function openPreview(file) {
  previewFile.value = file
}

async function handleNewChat() {
  currentView.value = 'chat'
  clearMessages()
  clearFiles()
  const convId = await create()
  select(convId)
  reloadConversations()
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

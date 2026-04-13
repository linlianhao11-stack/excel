<template>
  <!-- 未登录：显示登录页 -->
  <LoginPage v-if="!isLoggedIn" />

  <!-- 已登录：主界面 -->
  <div v-else class="h-screen flex bg-white">
    <!-- 侧边栏 -->
    <Sidebar
      @openSettings="showSettings = true"
      @newChat="handleNewChat"
      @selectConversation="handleSelectConversation"
    />

    <!-- 主区域 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶栏 -->
      <header class="h-13 border-b border-[#e5e5e5] flex items-center px-5 shrink-0">
        <!-- 已上传文件标签 -->
        <div class="flex items-center gap-2 overflow-x-auto">
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
      </header>

      <!-- 聊天区 -->
      <ChatPanel />
    </div>

    <!-- 设置弹窗 -->
    <SettingsModal v-if="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { FileSpreadsheet, X } from 'lucide-vue-next'
import { useAuth } from './composables/useAuth'
import { useFiles } from './composables/useFiles'
import { useChat } from './composables/useChat'
import { useConversations } from './composables/useConversations'
import LoginPage from './components/LoginPage.vue'
import Sidebar from './components/Sidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import SettingsModal from './components/SettingsModal.vue'

const { isLoggedIn } = useAuth()
const { files, remove, clear: clearFiles } = useFiles()
const { clearMessages, loadFromHistory } = useChat()
const { create, select, currentConvId } = useConversations()

const showSettings = ref(false)

async function handleNewChat() {
  clearMessages()
  clearFiles()
  const convId = await create()
  select(convId)
}

async function handleSelectConversation(convId) {
  clearMessages()
  clearFiles()
  select(convId)
  // 加载历史消息
  const { loadMessages } = useConversations()
  const data = await loadMessages(convId)
  if (data.messages) {
    loadFromHistory(data.messages)
  }
}
</script>

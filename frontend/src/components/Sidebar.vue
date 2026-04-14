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
    <SidebarHeader @newChat="$emit('newChat')" />
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

const emit = defineEmits(['openSettings', 'selectConversation', 'newChat'])

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

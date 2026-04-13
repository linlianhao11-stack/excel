<template>
  <div class="w-[260px] h-full bg-[#f9f9f9] border-r border-[#e5e5e5] flex flex-col shrink-0">
    <!-- 新对话按钮 -->
    <div class="p-3">
      <button
        @click="handleNewChat"
        class="w-full flex items-center gap-2 px-3 py-2 text-sm text-[#555] hover:bg-[#efefef] rounded-lg transition-colors"
      >
        <Plus class="w-4 h-4" />
        新对话
      </button>
    </div>

    <!-- 对话列表 -->
    <div class="flex-1 overflow-y-auto px-2">
      <template v-for="group in groupedConversations" :key="group.label">
        <div class="px-2 py-1.5 text-xs font-medium text-[#999] mt-2 first:mt-0">{{ group.label }}</div>
        <div
          v-for="conv in group.items"
          :key="conv.id"
          :class="[
            'group flex items-center gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer mb-0.5 transition-colors',
            currentConvId === conv.id ? 'bg-[#ebebeb] text-[#1a1a1a]' : 'text-[#555] hover:bg-[#efefef]'
          ]"
          @click="handleSelect(conv.id)"
        >
          <span class="flex-1 truncate">{{ conv.title }}</span>
          <button
            @click.stop="handleDelete(conv.id)"
            class="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-[#ddd] rounded transition-all"
          >
            <Trash2 class="w-3.5 h-3.5 text-[#999]" />
          </button>
        </div>
      </template>

      <div v-if="conversations.length === 0 && !loading" class="px-3 py-8 text-center text-xs text-[#999]">
        暂无对话记录
      </div>
    </div>

    <!-- 底部：用户信息 -->
    <div class="border-t border-[#e5e5e5] p-3">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-full bg-[#e5e5e5] flex items-center justify-center">
          <User class="w-4 h-4 text-[#555]" />
        </div>
        <span class="flex-1 text-sm text-[#555] truncate">{{ user?.username }}</span>
        <button
          @click="$emit('openSettings')"
          class="p-1 text-[#999] hover:text-[#555] hover:bg-[#efefef] rounded-md transition-colors"
          title="设置"
        >
          <Settings class="w-4 h-4" />
        </button>
        <button
          @click="handleLogout"
          class="p-1 text-[#999] hover:text-[#555] hover:bg-[#efefef] rounded-md transition-colors"
          title="退出登录"
        >
          <LogOut class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { Plus, Trash2, User, Settings, LogOut } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'
import { useConversations } from '../composables/useConversations'

const emit = defineEmits(['openSettings', 'selectConversation', 'newChat'])

const { user, logout } = useAuth()
const { conversations, currentConvId, loading, load, create, remove, select } = useConversations()

const groupedConversations = computed(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)

  const groups = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '最近 7 天', items: [] },
    { label: '更早', items: [] },
  ]

  for (const conv of conversations.value) {
    const date = new Date(conv.updated_at || conv.created_at)
    if (date >= today) groups[0].items.push(conv)
    else if (date >= yesterday) groups[1].items.push(conv)
    else if (date >= weekAgo) groups[2].items.push(conv)
    else groups[3].items.push(conv)
  }

  return groups.filter(g => g.items.length > 0)
})

function handleNewChat() {
  emit('newChat')
}

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

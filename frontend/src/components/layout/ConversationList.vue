<template>
  <div class="flex-1 overflow-y-auto px-2">
    <template v-for="group in groupedConversations" :key="group.label">
      <div class="px-2 py-1.5 text-xs font-medium mt-2 first:mt-0" style="color: var(--text-placeholder)">
        {{ group.label }}
      </div>
      <div
        v-for="conv in group.items"
        :key="conv.id"
        :class="[
          'group flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] cursor-pointer mb-0.5 transition-colors',
          currentConvId === conv.id ? 'font-medium' : ''
        ]"
        :style="{
          background: currentConvId === conv.id ? 'var(--surface-hover)' : 'transparent',
          color: currentConvId === conv.id ? 'var(--text)' : 'var(--text-secondary)'
        }"
        @click="$emit('select', conv.id)"
      >
        <MessageSquare class="w-3.5 h-3.5 shrink-0" />
        <span class="flex-1 truncate">{{ conv.title }}</span>
        <button
          @click.stop="$emit('delete', conv.id)"
          class="opacity-0 group-hover:opacity-100 p-0.5 rounded transition-all"
        >
          <Trash2 class="w-3.5 h-3.5" style="color: var(--text-placeholder)" />
        </button>
      </div>
    </template>
    <div
      v-if="conversations.length === 0 && !loading"
      class="px-3 py-8 text-center text-xs"
      style="color: var(--text-placeholder)"
    >
      暂无对话记录
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { MessageSquare, Trash2 } from 'lucide-vue-next'

const props = defineProps({
  conversations: { type: Array, default: () => [] },
  currentConvId: { type: [String, Number], default: null },
  loading: { type: Boolean, default: false }
})

defineEmits(['select', 'delete'])

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

  for (const conv of props.conversations) {
    const date = new Date(conv.updated_at || conv.created_at)
    if (date >= today) groups[0].items.push(conv)
    else if (date >= yesterday) groups[1].items.push(conv)
    else if (date >= weekAgo) groups[2].items.push(conv)
    else groups[3].items.push(conv)
  }

  return groups.filter(g => g.items.length > 0)
})
</script>

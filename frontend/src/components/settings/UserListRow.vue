<template>
  <div
    class="flex items-center gap-2 px-3.5 py-2.5 rounded-lg text-[14px]"
    :style="{ background: 'var(--background)' }"
  >
    <span class="flex-1" :style="{ color: 'var(--text)' }">{{ user.username }}</span>

    <span
      v-if="user.is_admin"
      class="text-[11px] font-medium px-2 py-0.5 rounded"
      :style="{ background: 'var(--warning-subtle)', color: 'var(--warning-emphasis)' }"
    >管理员</span>

    <span
      v-if="!user.is_active"
      class="text-[11px] font-medium px-2 py-0.5 rounded"
      :style="{ background: 'var(--error-subtle)', color: 'var(--error-emphasis)' }"
    >已禁用</span>

    <template v-if="user.id !== currentUserId">
      <button
        @click="$emit('resetPassword', user)"
        class="text-[12px] px-2 py-1 rounded hover:opacity-80 transition-opacity"
        :style="{ color: 'var(--text-muted)' }"
        title="重置密码"
      >
        <Key class="w-3.5 h-3.5" />
      </button>
      <button
        @click="$emit('toggleActive', user)"
        class="text-[12px] px-2 py-1 rounded hover:opacity-80 transition-opacity"
        :style="{ color: user.is_active ? 'var(--warning-emphasis)' : 'var(--success-emphasis)' }"
        :title="user.is_active ? '禁用' : '启用'"
      >
        <component :is="user.is_active ? Lock : Unlock" class="w-3.5 h-3.5" />
      </button>
      <button
        @click="$emit('deleteUser', user.id)"
        class="text-[12px] px-2 py-1 rounded hover:opacity-80 transition-opacity"
        :style="{ color: 'var(--text-placeholder)' }"
        title="删除"
      >
        <Trash2 class="w-3.5 h-3.5" />
      </button>
    </template>
  </div>
</template>

<script setup>
import { Key, Lock, Unlock, Trash2 } from 'lucide-vue-next'

defineProps({
  user: { type: Object, required: true },
  currentUserId: { type: [String, Number], default: null }
})
defineEmits(['resetPassword', 'toggleActive', 'deleteUser'])
</script>

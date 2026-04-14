<template>
  <div class="shrink-0 p-3" style="border-top: 1px solid var(--sidebar-border)">
    <div class="flex items-center gap-2">
      <div
        class="w-7 h-7 rounded-full flex items-center justify-center"
        style="background: var(--surface-hover)"
      >
        <User class="w-4 h-4" style="color: var(--text-secondary)" />
      </div>
      <span class="flex-1 text-[13px] truncate" style="color: var(--text-secondary)">
        {{ username }}
      </span>
      <button
        @click="$emit('openSettings')"
        class="p-1 rounded-md transition-colors"
        title="设置"
      >
        <Settings class="w-4 h-4" style="color: var(--text-placeholder)" />
      </button>
      <button
        @click="$emit('logout')"
        class="p-1 rounded-md transition-colors"
        title="退出登录"
      >
        <LogOut class="w-4 h-4" style="color: var(--text-placeholder)" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { User, Settings, LogOut } from 'lucide-vue-next'

defineProps({
  username: { type: String, default: '' }
})

defineEmits(['openSettings', 'logout'])
</script>

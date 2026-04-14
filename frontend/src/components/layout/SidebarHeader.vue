<template>
  <div class="shrink-0 flex items-center gap-2 px-4 pt-4 pb-3">
    <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background: var(--primary)">
      <FileSpreadsheet class="w-4 h-4 text-white" />
    </div>
    <span class="text-[15px] font-semibold" style="color: var(--text)">Excel Agent</span>
    <button
      class="ml-auto w-7 h-7 rounded-lg flex items-center justify-center cursor-pointer transition-colors"
      style="color: var(--text-secondary)"
      title="新对话"
      @click="$emit('newChat')"
      @mouseenter="$event.target.style.background = 'var(--sidebar-active-bg)'"
      @mouseleave="$event.target.style.background = 'transparent'"
    >
      <SquarePen class="w-4 h-4" />
    </button>
  </div>
</template>

<script setup>
import { FileSpreadsheet, SquarePen } from 'lucide-vue-next'

defineEmits(['newChat'])
</script>

<template>
  <div class="absolute top-0 left-0 right-0 flex items-center justify-between p-3 z-10 pointer-events-none">
    <button
      @click="toggle"
      class="p-1.5 rounded-lg transition-colors pointer-events-auto"
      title="切换侧边栏"
    >
      <PanelLeft class="w-5 h-5" style="color: var(--text-muted)" />
    </button>
    <button
      @click="$emit('newChat')"
      class="p-1.5 rounded-lg transition-colors pointer-events-auto"
      title="新对话"
    >
      <SquarePen class="w-5 h-5" style="color: var(--text-muted)" />
    </button>
  </div>
</template>

<script setup>
import { PanelLeft, SquarePen } from 'lucide-vue-next'
import { useSidebar } from '../../composables/useSidebar'

const { toggle } = useSidebar()

defineEmits(['newChat'])
</script>

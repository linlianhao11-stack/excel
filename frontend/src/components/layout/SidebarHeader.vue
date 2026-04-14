<template>
  <div class="shrink-0 flex items-center gap-2 px-4 pt-4 pb-3">
    <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background: var(--primary)">
      <FileSpreadsheet class="w-4 h-4 text-white" />
    </div>
    <span class="text-[15px] font-semibold" style="color: var(--text)">Excel Agent</span>
  </div>
</template>

<script setup>
import { FileSpreadsheet } from 'lucide-vue-next'
</script>

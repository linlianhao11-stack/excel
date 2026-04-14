<template>
  <div v-if="files.length || images.length" class="flex flex-wrap gap-2 px-3 pt-2.5">
    <!-- Excel 文件标签 -->
    <div
      v-for="f in files"
      :key="f.file_id"
      class="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-[12px] font-medium rounded-lg cursor-pointer transition-colors border"
      style="background: var(--elevated); border-color: var(--border); color: var(--text-secondary)"
      @click="$emit('previewFile', f)"
    >
      <FileSpreadsheet class="w-3.5 h-3.5" style="color: var(--success-emphasis)" />
      {{ f.filename }}
      <button
        @click.stop="$emit('removeFile', f.file_id)"
        class="ml-0.5 transition-colors"
        style="color: var(--text-placeholder)"
      >
        <X class="w-3 h-3" />
      </button>
    </div>

    <!-- 图片缩略图 -->
    <div
      v-for="img in images"
      :key="img.file_id"
      class="relative group w-12 h-12 rounded-lg overflow-hidden border"
      style="border-color: var(--border)"
    >
      <img :src="img.previewUrl" class="w-full h-full object-cover" />
      <button
        @click="$emit('removeImage', img.file_id)"
        class="absolute -top-1 -right-1 w-5 h-5 bg-black/60 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <X class="w-3 h-3" />
      </button>
    </div>
  </div>
</template>

<script setup>
import { FileSpreadsheet, X } from 'lucide-vue-next'

defineProps({
  files: { type: Array, default: () => [] },
  images: { type: Array, default: () => [] }
})

defineEmits(['removeFile', 'removeImage', 'previewFile'])
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="$emit('close')">
    <div class="bg-white rounded-2xl w-full max-w-4xl mx-4 shadow-xl max-h-[85vh] flex flex-col">
      <!-- 头部 -->
      <div class="flex items-center justify-between px-5 py-3 border-b border-[#e5e5e5] shrink-0">
        <div class="flex items-center gap-2 min-w-0">
          <FileSpreadsheet class="w-4 h-4 text-green-600 shrink-0" />
          <span class="text-sm font-semibold text-[#1a1a1a] truncate">{{ filename }}</span>
        </div>
        <button @click="$emit('close')" class="p-1 text-[#999] hover:text-[#555] rounded-md hover:bg-[#f4f4f4] shrink-0">
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Sheet 标签 -->
      <div v-if="sheetNames.length > 1" class="flex border-b border-[#e5e5e5] px-4 shrink-0 overflow-x-auto">
        <button
          v-for="name in sheetNames"
          :key="name"
          @click="activeSheet = name"
          :class="[
            'px-3 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap',
            activeSheet === name
              ? 'border-[#1a1a1a] text-[#1a1a1a]'
              : 'border-transparent text-[#999] hover:text-[#555]'
          ]"
        >
          {{ name }}
        </button>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="flex-1 flex items-center justify-center p-8">
        <div class="flex items-center gap-2 text-[#999] text-sm">
          <div class="w-4 h-4 border-2 border-[#ddd] border-t-[#555] rounded-full animate-spin" />
          加载中...
        </div>
      </div>

      <!-- 表格 -->
      <div v-else-if="currentSheet" class="flex-1 overflow-auto min-h-0">
        <table class="w-full text-sm border-collapse">
          <thead class="sticky top-0 z-10">
            <tr class="bg-[#f4f4f4]">
              <th class="px-3 py-2 text-left text-xs font-semibold text-[#999] border-b border-r border-[#e5e5e5] bg-[#f4f4f4] w-10">#</th>
              <th
                v-for="col in currentSheet.columns"
                :key="col"
                class="px-3 py-2 text-left text-xs font-semibold text-[#555] border-b border-r border-[#e5e5e5] bg-[#f4f4f4] whitespace-nowrap"
              >
                {{ col }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, i) in currentSheet.data"
              :key="i"
              class="hover:bg-[#fafafa] transition-colors"
            >
              <td class="px-3 py-1.5 text-xs text-[#999] border-b border-r border-[#f0f0f0] w-10">{{ i + 1 }}</td>
              <td
                v-for="(cell, j) in row"
                :key="j"
                class="px-3 py-1.5 text-[13px] text-[#1a1a1a] border-b border-r border-[#f0f0f0] max-w-[200px] truncate whitespace-nowrap"
                :title="cell"
              >
                {{ cell }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 底部信息栏 -->
      <div v-if="currentSheet" class="px-5 py-2 border-t border-[#e5e5e5] text-xs text-[#999] shrink-0 flex items-center gap-4">
        <span>{{ currentSheet.row_count }} 行</span>
        <span>{{ currentSheet.col_count }} 列</span>
        <span v-if="currentSheet.data.length < currentSheet.row_count" class="text-orange-500">
          (预览前 {{ currentSheet.data.length }} 行)
        </span>
      </div>

      <!-- 错误 -->
      <div v-if="error" class="p-6 text-center text-red-500 text-sm">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { FileSpreadsheet, X } from 'lucide-vue-next'
import { getExcelPreview } from '../api'

const props = defineProps({
  fileId: { type: String, required: true },
  filename: { type: String, required: true },
})
defineEmits(['close'])

const loading = ref(true)
const error = ref('')
const sheets = ref({})
const activeSheet = ref('')

const sheetNames = computed(() => Object.keys(sheets.value))
const currentSheet = computed(() => sheets.value[activeSheet.value])

onMounted(async () => {
  try {
    sheets.value = await getExcelPreview(props.fileId)
    const names = Object.keys(sheets.value)
    if (names.length) activeSheet.value = names[0]
  } catch (e) {
    error.value = e.response?.data?.detail || '预览加载失败'
  } finally {
    loading.value = false
  }
})
</script>

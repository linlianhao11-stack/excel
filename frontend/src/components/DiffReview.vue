<template>
  <div class="border border-[#e5e5e5] rounded-xl overflow-hidden bg-white">
    <!-- 标题 -->
    <div class="px-5 pt-4 pb-3">
      <h3 class="text-base font-semibold text-[#1a1a1a]">
        {{ approved ? '已确认' : '帮你改好了，确认一下？' }}
      </h3>
      <p class="text-sm text-[#888] mt-1">{{ summaryText }}</p>
    </div>

    <!-- 安全提示 -->
    <div
      :class="[
        'flex items-center gap-2 px-5 py-2.5 text-sm font-medium',
        integrityOk ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
      ]"
    >
      <component :is="integrityOk ? ShieldCheck : AlertTriangle" class="w-4 h-4 shrink-0" />
      {{ integrityOk ? '其他数据都检查过了，没有被误改' : '注意：有数据可能被误改了，请仔细检查' }}
    </div>

    <!-- 改动清单 -->
    <div class="divide-y divide-[#f0f0f0]">
      <div
        v-for="(item, i) in visibleChanges"
        :key="i"
        class="flex gap-3 px-5 py-3"
      >
        <!-- 标签 -->
        <span
          :class="[
            'shrink-0 text-xs font-semibold px-2 py-0.5 rounded mt-0.5',
            item.type === 'modified' ? 'bg-amber-100 text-amber-800' :
            item.type === 'added' ? 'bg-green-100 text-green-800' :
            'bg-red-100 text-red-800'
          ]"
        >
          {{ item.type === 'modified' ? '改' : item.type === 'added' ? '加' : '删' }}
        </span>

        <!-- 内容 -->
        <div class="flex-1 min-w-0">
          <!-- 修改 -->
          <template v-if="item.type === 'modified'">
            <p class="text-sm text-[#1a1a1a]">
              {{ item.row_label || `第${item.row}行` }} 的「{{ item.col_name }}」
            </p>
            <div class="flex items-center gap-1.5 mt-1 flex-wrap">
              <span class="text-xs bg-red-100 text-red-800 px-1.5 py-0.5 rounded">{{ item.old }}</span>
              <span class="text-xs text-[#ccc]">→</span>
              <span class="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded">{{ item.new }}</span>
            </div>
          </template>

          <!-- 新增 -->
          <template v-else-if="item.type === 'added'">
            <p class="text-sm text-[#1a1a1a]">新加了一行数据（第{{ item.row }}行）</p>
            <p class="text-xs text-[#888] mt-0.5">{{ formatRowData(item.data) }}</p>
          </template>

          <!-- 删除 -->
          <template v-else>
            <p class="text-sm text-[#1a1a1a]">删掉了{{ item.row_label || `第${item.row}行` }}</p>
            <p class="text-xs text-[#888] mt-0.5">{{ formatRowData(item.data) }}</p>
          </template>
        </div>
      </div>

      <!-- 折叠提示 -->
      <button
        v-if="hasMore"
        class="w-full px-5 py-2.5 text-sm text-[#3B63C9] hover:bg-[#f8f8f8] transition-colors text-center cursor-pointer"
        @click="showAll = !showAll"
      >
        {{ showAll ? '收起' : `还有 ${diff.total_changes - 20} 条改动，点击展开` }}
      </button>
    </div>

    <!-- 数值校验 -->
    <div v-if="sumChecks.length" class="px-5 py-3 bg-[#fafafa] border-t border-[#f0f0f0]">
      <div v-for="(sc, i) in sumChecks" :key="i" class="text-sm text-[#555]">
        「{{ sc.column }}」总数从 {{ sc.before }} 变成 {{ sc.after }}，{{ sc.diff > 0 ? '多' : '少' }}了 {{ Math.abs(sc.diff) }}
      </div>
    </div>

    <!-- 底栏按钮 -->
    <div v-if="!approved" class="flex items-center justify-end gap-3 px-5 py-3 border-t border-[#e5e5e5]">
      <button
        @click="showRejectModal = true"
        class="px-4 py-2 text-sm text-[#555] border border-[#d5d5d5] rounded-lg hover:bg-[#f5f5f5] transition-colors cursor-pointer"
      >
        不对，重新改
      </button>
      <button
        @click="handleApprove"
        :disabled="approving"
        class="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-white bg-[#3B63C9] rounded-lg hover:bg-[#2B51B1] transition-colors cursor-pointer disabled:opacity-50"
      >
        <Download class="w-4 h-4" />
        {{ approving ? '处理中...' : '没问题，下载文件' }}
      </button>
    </div>

    <!-- 驳回弹窗 -->
    <RejectModal
      v-if="showRejectModal"
      @confirm="handleReject"
      @cancel="showRejectModal = false"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ShieldCheck, AlertTriangle, Download } from 'lucide-vue-next'
import { approveDiff, downloadFile } from '../api'
import { useChat } from '../composables/useChat'
import RejectModal from './RejectModal.vue'

const props = defineProps({
  diff: { type: Object, required: true },
  conversationId: { type: String, default: null },
})

const emit = defineEmits(['approved'])

const { retryFromReject } = useChat()

const approved = ref(false)
const approving = ref(false)
const showRejectModal = ref(false)
const showAll = ref(false)

const integrityOk = computed(() => props.diff.integrity?.unchanged_rows_ok !== false)

const sumChecks = computed(() => props.diff.integrity?.sum_checks || [])

const summaryText = computed(() => {
  const s = props.diff.summary || {}
  const parts = []
  if (s.modified) parts.push(`改了 ${s.modified} 个格子`)
  if (s.added) parts.push(`加了 ${s.added} 行新数据`)
  if (s.deleted) parts.push(`删了 ${s.deleted} 行`)
  if (s.unchanged) parts.push(`其余 ${s.unchanged} 行没动过`)
  return parts.join('，') + '。'
})

const hasMore = computed(() => {
  const total = props.diff.total_changes || props.diff.changes?.length || 0
  return total > 20
})

const visibleChanges = computed(() => {
  const changes = props.diff.changes || []
  if (showAll.value) return changes
  return changes.slice(0, 20)
})

function formatRowData(data) {
  if (!data) return ''
  return Object.entries(data).map(([k, v]) => `${v}`).join(' | ')
}

async function handleApprove() {
  if (!props.conversationId) return
  approving.value = true
  try {
    const result = await approveDiff(props.conversationId)
    if (result.output_path) {
      approved.value = true
      emit('approved', result.output_path, result.output_display_name)
      await downloadFile(result.output_path, result.output_display_name)
    } else if (result.error) {
      alert(result.error)
    }
  } catch (e) {
    alert('审批失败，请重试')
  } finally {
    approving.value = false
  }
}

function handleReject({ reasonType, reasonText }) {
  showRejectModal.value = false
  if (!props.conversationId) return
  retryFromReject(props.conversationId, reasonType, reasonText)
}
</script>

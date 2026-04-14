<template>
  <div :class="['mb-6', message.role === 'user' ? 'flex justify-end' : '']">
    <!-- 用户消息 -->
    <div
      v-if="message.role === 'user'"
      class="max-w-lg"
    >
      <div v-if="message.images?.length" class="flex flex-wrap gap-2 mb-2 justify-end">
        <img
          v-for="(src, i) in message.images"
          :key="i"
          :src="src"
          class="max-w-[200px] max-h-[160px] rounded-xl border border-[#e5e5e5] object-contain cursor-pointer hover:shadow-md transition-shadow"
          @click="openImagePreview(src)"
        />
      </div>
      <div class="px-4 py-2.5 bg-[#f4f4f4] rounded-3xl text-[#1a1a1a] text-[15px] leading-relaxed">
        {{ message.content }}
      </div>
    </div>

    <!-- AI 消息 -->
    <div v-else class="space-y-3">
      <!-- 文本内容 -->
      <div
        v-if="message.content"
        class="text-[15px] text-[#1a1a1a] leading-[1.7] prose prose-sm max-w-none prose-pre:bg-[#1e1e1e] prose-pre:text-gray-100 prose-code:text-orange-600 prose-code:before:content-none prose-code:after:content-none"
        v-html="renderMarkdown(message.content)"
      />

      <!-- 工具调用（分组） -->
      <div
        v-for="(group, gi) in groupedToolCalls"
        :key="gi"
        class="border border-[#e5e5e5] rounded-xl overflow-hidden text-sm"
      >
        <!-- 单个调用：保持原样 -->
        <template v-if="group.calls.length === 1">
          <div
            class="flex items-center gap-2 px-3 py-2 bg-[#fafafa] border-b border-[#e5e5e5] cursor-pointer select-none hover:bg-[#f0f0f0] transition-colors"
            @click="group.calls[0].expanded = !group.calls[0].expanded"
          >
            <div class="w-5 h-5 rounded-md flex items-center justify-center" :class="group.name === 'query' ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'">
              <component :is="group.name === 'query' ? Search : Play" class="w-3 h-3" />
            </div>
            <span class="font-medium text-[#555] shrink-0">{{ toolLabel(group.name) }}</span>
            <span class="text-xs text-[#aaa] truncate font-mono">{{ codePreview(group.calls[0].code) }}</span>
            <span v-if="group.calls[0].result !== null" class="text-xs text-green-600 shrink-0">完成</span>
            <span v-else class="text-xs text-orange-500 shrink-0 animate-pulse">运行中...</span>
            <ChevronDown
              :class="['w-4 h-4 text-[#999] shrink-0 transition-transform duration-200', group.calls[0].expanded ? 'rotate-180' : '']"
            />
          </div>
          <div v-show="group.calls[0].expanded" class="divide-y divide-[#e5e5e5]">
            <pre class="px-4 py-3 bg-[#1e1e1e] text-[13px] text-gray-100 overflow-x-auto leading-relaxed"><code>{{ group.calls[0].code }}</code></pre>
            <pre
              v-if="group.calls[0].result"
              class="px-4 py-3 bg-white text-[13px] text-[#555] overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto"
            >{{ group.calls[0].result }}</pre>
          </div>
        </template>

        <!-- 多个同类调用：分组折叠 -->
        <template v-else>
          <!-- 组标题 -->
          <div
            class="flex items-center gap-2 px-3 py-2 bg-[#fafafa] cursor-pointer select-none hover:bg-[#f0f0f0] transition-colors"
            @click="toggleGroup(gi)"
          >
            <div class="w-5 h-5 rounded-md flex items-center justify-center" :class="group.name === 'query' ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'">
              <component :is="group.name === 'query' ? Search : Play" class="w-3 h-3" />
            </div>
            <span class="font-medium text-[#555] shrink-0">{{ toolLabel(group.name) }}</span>
            <span class="text-xs text-[#888] bg-[#eee] px-1.5 py-0.5 rounded-full font-medium shrink-0">{{ group.calls.length }}</span>
            <span v-if="groupAllDone(group)" class="text-xs text-green-600 shrink-0">完成</span>
            <span v-else class="text-xs text-orange-500 shrink-0 animate-pulse">{{ groupDoneCount(group) }}/{{ group.calls.length }}</span>
            <ChevronDown
              :class="['w-4 h-4 text-[#999] shrink-0 transition-transform duration-200', groupExpanded[gi] ? 'rotate-180' : '']"
            />
          </div>

          <!-- 组内明细 -->
          <div v-show="groupExpanded[gi]" class="max-h-80 overflow-y-auto">
            <div
              v-for="(tc, ci) in group.calls"
              :key="ci"
              class="border-t border-[#e5e5e5]"
            >
              <div
                class="flex items-center gap-2 px-3 py-1.5 bg-white cursor-pointer hover:bg-[#fafafa] transition-colors"
                @click="tc.expanded = !tc.expanded"
              >
                <span class="text-[11px] text-[#bbb] w-5 text-right shrink-0 font-mono">#{{ ci + 1 }}</span>
                <span class="text-xs text-[#777] truncate flex-1 font-mono">{{ codePreview(tc.code) }}</span>
                <span v-if="tc.result !== null" class="text-green-500 text-xs shrink-0">&#10003;</span>
                <span v-else class="text-orange-400 text-xs shrink-0 animate-pulse">&#9679;</span>
                <ChevronDown :class="['w-3 h-3 text-[#ccc] shrink-0 transition-transform duration-200', tc.expanded ? 'rotate-180' : '']" />
              </div>
              <div v-show="tc.expanded" class="divide-y divide-[#e5e5e5]">
                <pre class="px-4 py-3 bg-[#1e1e1e] text-[13px] text-gray-100 overflow-x-auto leading-relaxed"><code>{{ tc.code }}</code></pre>
                <pre
                  v-if="tc.result"
                  class="px-4 py-3 bg-white text-[13px] text-[#555] overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto"
                >{{ tc.result }}</pre>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Diff 审查面板 -->
      <DiffReview
        v-if="message.diff"
        :diff="message.diff"
        :conversationId="message.conversationId"
        @approved="onDiffApproved"
      />

      <!-- Create 摘要 -->
      <div v-if="message.createSummary && !message.createSummary.error" class="border border-[#e5e5e5] rounded-xl overflow-hidden bg-white">
        <div class="px-5 py-3">
          <h3 class="text-sm font-semibold text-[#1a1a1a]">新文件已生成</h3>
          <div v-for="(sheet, name) in message.createSummary.sheets" :key="name" class="mt-2 text-sm text-[#555]">
            <span class="font-medium">{{ name }}</span>：{{ sheet.row_count }} 行 × {{ sheet.col_count }} 列
          </div>
        </div>
      </div>

      <!-- 下载按钮（审批通过后 或 create 模式） -->
      <button
        v-if="message.outputPath"
        @click="handleDownload(message.outputPath)"
        class="inline-flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] hover:bg-[#333] text-white text-sm font-medium rounded-xl transition-colors cursor-pointer"
      >
        <Download class="w-4 h-4" />
        下载结果文件
      </button>

      <!-- 错误 -->
      <div
        v-if="message.error"
        class="px-4 py-3 bg-red-50 text-red-600 text-sm rounded-xl border border-red-200"
      >
        {{ message.error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { Search, Play, Download, ChevronDown } from 'lucide-vue-next'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { downloadFile } from '../api'
import DiffReview from './DiffReview.vue'

const props = defineProps({ message: Object })

function onDiffApproved(outputPath) {
  props.message.outputPath = outputPath
}

// 分组展开状态
const groupExpanded = reactive({})

// 将连续同名工具调用分组
const groupedToolCalls = computed(() => {
  const groups = []
  for (const tc of props.message.toolCalls || []) {
    const last = groups[groups.length - 1]
    if (last && last.name === tc.name) {
      last.calls.push(tc)
    } else {
      groups.push({ name: tc.name, calls: [tc] })
    }
  }
  return groups
})

function toggleGroup(gi) {
  groupExpanded[gi] = !groupExpanded[gi]
}

function groupAllDone(group) {
  return group.calls.every(tc => tc.result !== null)
}

function groupDoneCount(group) {
  return group.calls.filter(tc => tc.result !== null).length
}

function toolLabel(name) {
  if (name === 'query') return '探索数据'
  if (name === 'modify') return '修改文件'
  if (name === 'create') return '生成文件'
  return '执行处理'
}

function codePreview(code) {
  if (!code) return '...'
  const lines = code.split('\n').filter(l => l.trim() && !l.trim().startsWith('#'))
  return lines[0]?.trim().slice(0, 80) || '...'
}

function openImagePreview(src) {
  window.open(src, '_blank')
}

function renderMarkdown(text) {
  const html = marked.parse(text, { breaks: true })
  return DOMPurify.sanitize(html)
}

async function handleDownload(path) {
  try {
    await downloadFile(path)
  } catch {
    alert('下载失败，请重试')
  }
}
</script>

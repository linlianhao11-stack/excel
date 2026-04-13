<template>
  <div :class="['mb-6', message.role === 'user' ? 'flex justify-end' : '']">
    <!-- 用户消息 -->
    <div
      v-if="message.role === 'user'"
      class="max-w-lg px-4 py-2.5 bg-[#f4f4f4] rounded-3xl text-[#1a1a1a] text-[15px] leading-relaxed"
    >
      {{ message.content }}
    </div>

    <!-- AI 消息 -->
    <div v-else class="space-y-3">
      <!-- 文本内容 -->
      <div
        v-if="message.content"
        class="text-[15px] text-[#1a1a1a] leading-[1.7] prose prose-sm max-w-none prose-pre:bg-[#1e1e1e] prose-pre:text-gray-100 prose-code:text-orange-600 prose-code:before:content-none prose-code:after:content-none"
        v-html="renderMarkdown(message.content)"
      />

      <!-- 工具调用 -->
      <div
        v-for="(tc, i) in message.toolCalls"
        :key="i"
        class="border border-[#e5e5e5] rounded-xl overflow-hidden text-sm"
      >
        <div
          class="flex items-center gap-2 px-3 py-2 bg-[#fafafa] border-b border-[#e5e5e5] cursor-pointer select-none hover:bg-[#f0f0f0] transition-colors"
          @click="tc.expanded = !tc.expanded"
        >
          <div class="w-5 h-5 rounded-md flex items-center justify-center" :class="tc.name === 'query' ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'">
            <component :is="tc.name === 'query' ? Search : Play" class="w-3 h-3" />
          </div>
          <span class="font-medium text-[#555]">{{ tc.name === 'query' ? '探索数据' : '执行处理' }}</span>
          <span v-if="tc.result" class="text-xs text-green-600 ml-1">完成</span>
          <span v-else class="text-xs text-orange-500 ml-1 animate-pulse">运行中...</span>
          <ChevronDown
            :class="['w-4 h-4 text-[#999] ml-auto transition-transform duration-200', tc.expanded ? 'rotate-180' : '']"
          />
        </div>
        <div v-show="tc.expanded" class="divide-y divide-[#e5e5e5]">
          <pre class="px-4 py-3 bg-[#1e1e1e] text-[13px] text-gray-100 overflow-x-auto leading-relaxed"><code>{{ tc.code }}</code></pre>
          <pre
            v-if="tc.result"
            class="px-4 py-3 bg-white text-[13px] text-[#555] overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto"
          >{{ tc.result }}</pre>
        </div>
      </div>

      <!-- 下载按钮 -->
      <a
        v-if="message.outputPath"
        :href="getDownloadUrl(message.outputPath)"
        class="inline-flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] hover:bg-[#333] text-white text-sm font-medium rounded-xl transition-colors"
      >
        <Download class="w-4 h-4" />
        下载结果文件
      </a>

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
import { Search, Play, Download, ChevronDown } from 'lucide-vue-next'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { getDownloadUrl } from '../api'

defineProps({ message: Object })

function renderMarkdown(text) {
  const html = marked.parse(text, { breaks: true })
  return DOMPurify.sanitize(html)
}
</script>

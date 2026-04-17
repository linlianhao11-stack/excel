<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    @click.self="$emit('close')"
  >
    <div
      class="rounded-2xl shadow-xl w-full max-w-4xl mx-4 flex flex-col"
      :style="{ background: 'var(--surface)', maxHeight: '85vh' }"
    >
      <!-- 头部 -->
      <div class="px-6 py-4 border-b flex items-center justify-between" :style="{ borderColor: 'var(--border)' }">
        <div>
          <h3 class="text-base font-semibold" :style="{ color: 'var(--text)' }">
            {{ conversation?.title || '未命名对话' }}
          </h3>
          <p class="text-sm mt-0.5" :style="{ color: 'var(--text-muted)' }">
            <span class="inline-flex items-center gap-1">
              <User class="w-3.5 h-3.5" />
              {{ conversation?.owner_username }}
            </span>
            <span class="mx-2">·</span>
            <span>更新于 {{ formatTime(conversation?.updated_at) }}</span>
          </p>
        </div>
        <button
          @click="$emit('close')"
          class="p-1.5 rounded-lg hover:opacity-70 transition-opacity"
          :style="{ color: 'var(--text-muted)' }"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- 内容区（滚动） -->
      <div class="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        <!-- 附件 -->
        <div v-if="files.length" class="space-y-2">
          <h4 class="text-[13px] font-medium flex items-center gap-1.5" :style="{ color: 'var(--text-muted)' }">
            <Paperclip class="w-3.5 h-3.5" /> 附件（{{ files.length }}）
          </h4>
          <div class="space-y-1">
            <div
              v-for="f in files"
              :key="f.file_id"
              class="text-[13px] px-3 py-2 rounded-lg"
              :style="{ background: 'var(--background)', color: 'var(--text)' }"
            >
              📎 {{ f.filename }}
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div class="space-y-3">
          <h4 class="text-[13px] font-medium" :style="{ color: 'var(--text-muted)' }">
            消息记录（{{ messages.length }}）
          </h4>
          <div
            v-for="m in messages"
            :key="m.id"
            class="rounded-xl px-4 py-3"
            :style="{
              background: m.role === 'user' ? 'var(--primary-muted)' : 'var(--background)',
            }"
          >
            <div class="flex items-center gap-2 text-[12px] mb-1.5" :style="{ color: 'var(--text-muted)' }">
              <span class="font-medium" :style="{ color: 'var(--text)' }">
                {{ m.role === 'user' ? '👤 用户' : '🤖 助手' }}
              </span>
              <span>·</span>
              <span>{{ formatTime(m.created_at) }}</span>
            </div>
            <div v-if="m.content" class="text-[14px] whitespace-pre-wrap" :style="{ color: 'var(--text)' }">
              {{ m.content }}
            </div>
            <div v-if="m.output_path" class="mt-2">
              <button
                @click="handleDownload(m.output_path, m.output_display_name)"
                class="inline-flex items-center gap-1.5 text-[13px] px-3 py-1.5 rounded-lg transition-colors"
                :style="{ background: 'var(--primary)', color: 'white' }"
              >
                <Download class="w-3.5 h-3.5" />
                {{ m.output_display_name || '下载结果' }}
              </button>
            </div>
            <div v-if="m.error" class="mt-2 text-[13px]" :style="{ color: 'var(--error-emphasis)' }">
              ❌ {{ m.error }}
            </div>
          </div>
          <div v-if="!messages.length" class="text-[13px] py-8 text-center" :style="{ color: 'var(--text-muted)' }">
            暂无消息
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { User, X, Paperclip, Download } from 'lucide-vue-next'
import { getConversationMessages, downloadFile } from '../../api'

const props = defineProps({
  conversation: { type: Object, default: null }
})
defineEmits(['close'])

const messages = ref([])
const files = ref([])

watch(() => props.conversation, async (conv) => {
  if (!conv) return
  try {
    const data = await getConversationMessages(conv.id)
    messages.value = data.messages || []
    files.value = data.files || []
  } catch {
    messages.value = []
    files.value = []
  }
}, { immediate: true })

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay} 天前`
  return d.toLocaleDateString('zh-CN')
}

async function handleDownload(path, displayName) {
  try {
    await downloadFile(path, displayName)
  } catch {
    alert('下载失败')
  }
}
</script>

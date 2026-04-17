<template>
  <section class="space-y-4">
    <div class="flex items-center gap-2">
      <Database class="w-[18px] h-[18px]" :style="{ color: 'var(--primary)' }" />
      <h2 class="text-base font-semibold" :style="{ color: 'var(--text)' }">全局对话管理</h2>
      <span
        class="text-[11px] font-medium px-2 py-0.5 rounded"
        :style="{ background: 'var(--primary-muted)', color: 'var(--primary)' }"
      >仅管理员</span>
    </div>

    <p class="text-[13px]" :style="{ color: 'var(--text-muted)' }">
      共 {{ conversations.length }} 条对话，来自 {{ uniqueUserCount }} 个用户
    </p>

    <!-- 表格容器：小屏横向滚动，保证每列不挤压 -->
    <div class="rounded-xl border overflow-x-auto" :style="{ borderColor: 'var(--border)' }">
      <table class="w-full text-[13px]" style="min-width: 720px">
        <thead :style="{ background: 'var(--background)' }">
          <tr>
            <th class="px-4 py-3 text-left font-medium whitespace-nowrap" :style="{ color: 'var(--text-muted)', minWidth: '110px' }">用户</th>
            <th class="px-4 py-3 text-left font-medium" :style="{ color: 'var(--text-muted)', minWidth: '200px' }">对话标题</th>
            <th class="px-4 py-3 text-left font-medium whitespace-nowrap" :style="{ color: 'var(--text-muted)', minWidth: '110px' }">更新时间</th>
            <th class="px-4 py-3 text-center font-medium whitespace-nowrap" :style="{ color: 'var(--text-muted)', minWidth: '64px' }">消息</th>
            <th class="px-4 py-3 text-center font-medium whitespace-nowrap" :style="{ color: 'var(--text-muted)', minWidth: '64px' }">文件</th>
            <th class="px-4 py-3 text-right font-medium whitespace-nowrap" :style="{ color: 'var(--text-muted)', minWidth: '140px' }">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in conversations"
            :key="c.id"
            class="border-t transition-colors hover:opacity-90"
            :style="{ borderColor: 'var(--border)' }"
          >
            <td class="px-4 py-3 whitespace-nowrap">
              <span
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium"
                :style="{ background: 'var(--primary)', color: 'white' }"
              >
                <User class="w-3 h-3" />
                {{ c.owner_username }}
              </span>
            </td>
            <td class="px-4 py-3" :style="{ color: 'var(--text)' }">
              {{ c.title || '未命名对话' }}
            </td>
            <td class="px-4 py-3 whitespace-nowrap" :style="{ color: 'var(--text-muted)' }">
              {{ formatTime(c.updated_at) }}
            </td>
            <td class="px-4 py-3 text-center">
              <span
                class="inline-block px-2 py-0.5 rounded text-[11px]"
                :style="{ background: 'var(--background)', color: 'var(--text-muted)' }"
              >{{ c.message_count }}</span>
            </td>
            <td class="px-4 py-3 text-center">
              <span
                class="inline-block px-2 py-0.5 rounded text-[11px]"
                :style="{ background: 'var(--background)', color: 'var(--text-muted)' }"
              >{{ c.file_count }}</span>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              <div class="flex items-center justify-end gap-2">
                <button
                  @click="preview = c"
                  class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
                  :style="{ background: 'var(--primary)', color: 'white' }"
                >查看</button>
                <button
                  @click="handleDelete(c)"
                  class="px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
                  :style="{ background: 'var(--error-subtle)', color: 'var(--error-emphasis)' }"
                >删除</button>
              </div>
            </td>
          </tr>
          <tr v-if="!conversations.length">
            <td colspan="6" class="px-4 py-8 text-center" :style="{ color: 'var(--text-muted)' }">
              暂无对话
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <ConversationPreviewModal
      v-if="preview"
      :conversation="preview"
      @close="preview = null"
    />
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Database, User } from 'lucide-vue-next'
import { listConversations, deleteConversation } from '../../api'
import ConversationPreviewModal from './ConversationPreviewModal.vue'

const conversations = ref([])
const preview = ref(null)

const uniqueUserCount = computed(() => {
  const set = new Set(conversations.value.map(c => c.owner_username))
  return set.size
})

async function load() {
  try {
    conversations.value = await listConversations('all')
  } catch { conversations.value = [] }
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  const now = new Date()
  const diffMin = Math.floor((now - d) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay} 天前`
  return d.toLocaleDateString('zh-CN')
}

async function handleDelete(c) {
  if (!confirm(`确定删除 ${c.owner_username} 的对话 "${c.title}" 吗？`)) return
  try {
    await deleteConversation(c.id)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || '删除失败')
  }
}

onMounted(load)
</script>

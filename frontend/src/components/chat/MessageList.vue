<template>
  <div ref="scrollContainer" class="flex-1 overflow-y-auto" @scroll="handleScroll">
    <div class="max-w-4xl mx-auto py-8 px-4">
      <MessageBubble
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- 状态指示器 -->
      <div
        v-if="status"
        class="flex items-center gap-2 text-[13px] mb-6 pl-0.5"
        style="color: var(--text-placeholder)"
      >
        <div class="flex gap-1" v-if="status === 'thinking'">
          <span class="w-1.5 h-1.5 rounded-full animate-pulse" style="background: var(--text-placeholder)" />
          <span class="w-1.5 h-1.5 rounded-full animate-pulse [animation-delay:150ms]" style="background: var(--text-placeholder)" />
          <span class="w-1.5 h-1.5 rounded-full animate-pulse [animation-delay:300ms]" style="background: var(--text-placeholder)" />
        </div>
        <svg v-else class="w-4 h-4 animate-spin" style="color: var(--text-placeholder)" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" opacity="0.25" />
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <span class="text-xs">{{ statusLabel }}</span>
        <span v-if="elapsed > 0" class="text-xs" style="color: var(--border-strong)">{{ elapsed }}s</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed, onUnmounted } from 'vue'
import MessageBubble from '../MessageBubble.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  status: { type: String, default: null }
})

const scrollContainer = ref(null)
const userScrolledUp = ref(false)
const elapsed = ref(0)
let timerInterval = null
let timerStart = 0

const statusLabel = computed(() => {
  switch (props.status) {
    case 'thinking': return '分析中'
    case 'running': return '执行代码中'
    case 'verifying': return '验证结果中'
    case 'reporting': return '生成报告中'
    default: return ''
  }
})

watch(() => props.status, (val) => {
  if (val) {
    timerStart = Date.now()
    elapsed.value = 0
    if (!timerInterval) {
      timerInterval = setInterval(() => {
        elapsed.value = Math.floor((Date.now() - timerStart) / 1000)
      }, 1000)
    }
  } else {
    if (timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
    elapsed.value = 0
  }
})

onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
})

function handleScroll() {
  const el = scrollContainer.value
  if (!el) return
  userScrolledUp.value = el.scrollHeight - el.scrollTop - el.clientHeight > 100
}

watch(
  () => {
    const last = props.messages[props.messages.length - 1]
    return last?.content?.length || last?.toolCalls?.length || props.messages.length
  },
  async () => {
    if (userScrolledUp.value) return
    await nextTick()
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  }
)
</script>

<template>
  <div class="relative" ref="wrapperRef">
    <button
      type="button"
      class="w-full flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg text-[14px] text-left transition-colors"
      :style="{
        border: '1px solid ' + (open ? 'var(--primary)' : 'var(--input-border)'),
        background: 'var(--surface)',
        color: modelValue ? 'var(--text)' : 'var(--text-placeholder)',
        boxShadow: open ? '0 0 0 3px var(--primary-ring)' : 'none'
      }"
      @click="open = !open"
    >
      <span class="truncate">{{ displayText }}</span>
      <ChevronDown
        class="w-4 h-4 shrink-0 transition-transform"
        :class="open ? 'rotate-180' : ''"
        style="color: var(--text-placeholder)"
      />
    </button>

    <!-- 下拉面板 -->
    <div
      v-if="open"
      class="absolute z-50 mt-1 w-full rounded-lg py-1 shadow-lg max-h-60 overflow-y-auto"
      :style="{
        background: 'var(--surface)',
        border: '1px solid var(--border)'
      }"
    >
      <button
        v-for="opt in normalizedOptions"
        :key="opt.value"
        type="button"
        class="w-full flex items-center gap-2 px-3 py-2 text-[14px] text-left transition-colors"
        :style="{
          background: opt.value === modelValue ? 'var(--primary-muted)' : 'transparent',
          color: opt.value === modelValue ? 'var(--primary)' : 'var(--text)'
        }"
        @mouseenter="$event.currentTarget.style.background = opt.value === modelValue ? 'var(--primary-muted)' : 'var(--elevated)'"
        @mouseleave="$event.currentTarget.style.background = opt.value === modelValue ? 'var(--primary-muted)' : 'transparent'"
        @click="selectOption(opt.value)"
      >
        <Check
          v-if="opt.value === modelValue"
          class="w-4 h-4 shrink-0"
          style="color: var(--primary)"
        />
        <span v-else class="w-4 shrink-0" />
        <span class="truncate">{{ opt.label }}</span>
      </button>
      <div
        v-if="normalizedOptions.length === 0"
        class="px-3 py-2 text-[13px]"
        style="color: var(--text-placeholder)"
      >
        暂无选项
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ChevronDown, Check } from 'lucide-vue-next'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '请选择' }
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const wrapperRef = ref(null)

const normalizedOptions = computed(() =>
  props.options.map(opt =>
    typeof opt === 'string' ? { value: opt, label: opt } : opt
  )
)

const displayText = computed(() => {
  const found = normalizedOptions.value.find(o => o.value === props.modelValue)
  return found ? found.label : props.placeholder
})

function selectOption(val) {
  emit('update:modelValue', val)
  open.value = false
}

function handleClickOutside(e) {
  if (wrapperRef.value && !wrapperRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <section class="space-y-5">
    <div class="flex items-center gap-2">
      <UserPlus class="w-[18px] h-[18px]" :style="{ color: 'var(--primary)' }" />
      <h2 class="text-base font-semibold" :style="{ color: 'var(--text)' }">开放注册</h2>
      <span
        class="text-[11px] font-medium px-2 py-0.5 rounded"
        :style="{ background: 'var(--primary-muted)', color: 'var(--primary)' }"
      >仅管理员</span>
    </div>

    <label class="flex items-center gap-3 max-w-md cursor-pointer">
      <input
        type="checkbox"
        :checked="modelValue"
        @change="$emit('update:modelValue', $event.target.checked)"
        class="w-4 h-4 accent-[color:var(--primary)]"
      />
      <div>
        <div class="text-[14px]" :style="{ color: 'var(--text)' }">允许新用户自行注册</div>
        <div class="text-[12px] mt-0.5" :style="{ color: 'var(--text-muted)' }">
          关闭后，登录页不再显示注册入口
        </div>
      </div>
    </label>
  </section>
</template>

<script setup>
import { UserPlus } from 'lucide-vue-next'

defineProps({ modelValue: { type: Boolean, default: true } })
defineEmits(['update:modelValue'])
</script>

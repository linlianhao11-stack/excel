<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    @click.self="$emit('cancel')"
  >
    <div class="rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden" :style="{ background: 'var(--surface)' }">
      <div class="px-6 pt-5 pb-2">
        <h3 class="text-base font-semibold" :style="{ color: 'var(--text)' }">重置密码</h3>
        <p class="text-sm mt-1" :style="{ color: 'var(--text-muted)' }">
          即将把 <strong :style="{ color: 'var(--text)' }">{{ username }}</strong> 的密码重置。请输入两次新密码确认。
        </p>
      </div>

      <div class="px-6 py-3 space-y-3">
        <input
          v-model="newPassword"
          type="password"
          placeholder="新密码"
          autocomplete="new-password"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none border"
          :style="{ borderColor: 'var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        />
        <input
          v-model="confirmPassword"
          type="password"
          placeholder="再次输入新密码"
          autocomplete="new-password"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none border"
          :style="{ borderColor: 'var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        />
        <div
          v-if="error"
          class="px-3 py-2 text-[13px] rounded-lg"
          :style="{ background: 'var(--error-subtle)', color: 'var(--error-emphasis)' }"
        >{{ error }}</div>
      </div>

      <div class="flex justify-end gap-2 px-6 py-4 border-t" :style="{ borderColor: 'var(--border)' }">
        <button
          @click="$emit('cancel')"
          class="px-4 py-2 text-sm rounded-lg transition-colors"
          :style="{ color: 'var(--text-muted)' }"
        >取消</button>
        <button
          @click="handleConfirm"
          :disabled="!newPassword || loading"
          class="px-4 py-2 text-sm text-white rounded-lg transition-colors disabled:opacity-50"
          :style="{ background: 'var(--primary)' }"
        >{{ loading ? '提交中...' : '确认重置' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  username: { type: String, required: true },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['confirm', 'cancel'])

const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')

function handleConfirm() {
  if (!newPassword.value) {
    error.value = '新密码不能为空'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  error.value = ''
  emit('confirm', newPassword.value)
}
</script>

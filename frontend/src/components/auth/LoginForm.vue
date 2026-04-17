<template>
  <form @submit.prevent="handleSubmit" class="space-y-4">
    <div>
      <input
        v-model="username"
        type="text"
        placeholder="用户名"
        autocomplete="username"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{
          borderColor: 'var(--input-border)',
          color: 'var(--text)',
        }"
      />
    </div>
    <div>
      <input
        v-model="password"
        type="password"
        placeholder="密码"
        autocomplete="current-password"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{
          borderColor: 'var(--input-border)',
          color: 'var(--text)',
        }"
      />
    </div>

    <div
      v-if="error"
      class="px-3 py-2 text-sm rounded-lg border"
      :style="{
        background: 'var(--error-subtle)',
        color: 'var(--error-emphasis)',
        borderColor: 'var(--error-subtle)',
      }"
    >{{ error }}</div>

    <div class="flex gap-2">
      <button
        type="submit"
        :disabled="loading"
        class="flex-1 py-2.5 text-white text-[15px] font-medium rounded-xl disabled:opacity-50 transition-colors"
        :style="{ background: 'var(--primary)' }"
      >
        {{ loading ? '登录中...' : '登录' }}
      </button>
      <button
        v-if="allowRegistration"
        type="button"
        @click="$emit('switchToRegister')"
        class="px-4 py-2.5 text-[15px] font-medium rounded-xl border transition-colors"
        :style="{ borderColor: 'var(--border)', color: 'var(--text)' }"
      >
        注册
      </button>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { useAuth } from '../../composables/useAuth'

defineProps({
  allowRegistration: { type: Boolean, default: false }
})
defineEmits(['switchToRegister'])

const { login } = useAuth()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  if (!username.value || !password.value) return
  error.value = ''
  loading.value = true
  try {
    await login(username.value, password.value)
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

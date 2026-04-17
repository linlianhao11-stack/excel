<template>
  <form @submit.prevent="handleSubmit" class="space-y-4">
    <div>
      <input
        v-model="username"
        type="text"
        placeholder="用户名"
        autocomplete="username"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)' }"
      />
    </div>
    <div>
      <input
        v-model="password"
        type="password"
        placeholder="密码"
        autocomplete="new-password"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)' }"
      />
    </div>
    <div>
      <input
        v-model="confirmPassword"
        type="password"
        placeholder="再次输入密码"
        autocomplete="new-password"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)' }"
      />
    </div>

    <div
      v-if="error"
      class="px-3 py-2 text-sm rounded-lg border"
      :style="{ background: 'var(--error-subtle)', color: 'var(--error-emphasis)', borderColor: 'var(--error-subtle)' }"
    >{{ error }}</div>

    <div class="flex gap-2">
      <button
        type="submit"
        :disabled="loading"
        class="flex-1 py-2.5 text-white text-[15px] font-medium rounded-xl disabled:opacity-50 transition-colors"
        :style="{ background: 'var(--primary)' }"
      >
        {{ loading ? '注册中...' : '注册' }}
      </button>
      <button
        type="button"
        @click="$emit('switchToLogin')"
        class="px-4 py-2.5 text-[15px] font-medium rounded-xl border transition-colors"
        :style="{ borderColor: 'var(--border)', color: 'var(--text)' }"
      >
        返回登录
      </button>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { useAuth } from '../../composables/useAuth'

defineEmits(['switchToLogin'])

const { register } = useAuth()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  if (!username.value || !password.value) {
    error.value = '用户名和密码不能为空'
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  error.value = ''
  loading.value = true
  try {
    await register(username.value, password.value)
  } catch (e) {
    error.value = e.response?.data?.detail || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

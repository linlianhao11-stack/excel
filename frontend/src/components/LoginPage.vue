<template>
  <div class="h-screen flex items-center justify-center bg-white">
    <div class="w-full max-w-sm px-6">
      <div class="flex flex-col items-center mb-8">
        <div class="w-12 h-12 rounded-2xl bg-[#1a1a1a] flex items-center justify-center mb-4">
          <FileSpreadsheet class="w-6 h-6 text-white" />
        </div>
        <h1 class="text-xl font-semibold text-[#1a1a1a]">Excel Agent</h1>
        <p class="text-sm text-[#999] mt-1">登录以继续</p>
      </div>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <input
            v-model="username"
            type="text"
            placeholder="用户名"
            autocomplete="username"
            class="w-full px-4 py-2.5 border border-[#d9d9d9] rounded-xl text-[15px] text-[#1a1a1a] placeholder-[#999] focus:outline-none focus:border-[#999] focus:ring-1 focus:ring-[#999] transition-all"
          />
        </div>
        <div>
          <input
            v-model="password"
            type="password"
            placeholder="密码"
            autocomplete="current-password"
            class="w-full px-4 py-2.5 border border-[#d9d9d9] rounded-xl text-[15px] text-[#1a1a1a] placeholder-[#999] focus:outline-none focus:border-[#999] focus:ring-1 focus:ring-[#999] transition-all"
          />
        </div>

        <div v-if="error" class="px-3 py-2 bg-red-50 text-red-600 text-sm rounded-lg border border-red-200">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-2.5 bg-[#1a1a1a] text-white text-[15px] font-medium rounded-xl hover:bg-[#333] disabled:opacity-50 transition-colors"
        >
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { FileSpreadsheet } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'

const { login } = useAuth()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
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

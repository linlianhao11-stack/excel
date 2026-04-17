<template>
  <div class="h-screen flex items-center justify-center" :style="{ background: 'var(--surface)' }">
    <div class="w-full max-w-sm px-6">
      <div class="flex flex-col items-center mb-8">
        <div class="w-12 h-12 rounded-2xl flex items-center justify-center mb-4" :style="{ background: 'var(--text)' }">
          <FileSpreadsheet class="w-6 h-6 text-white" />
        </div>
        <h1 class="text-xl font-semibold" :style="{ color: 'var(--text)' }">Excel Agent</h1>
        <p class="text-sm mt-1" :style="{ color: 'var(--text-muted)' }">
          {{ mode === 'login' ? '登录以继续' : '创建新账号' }}
        </p>
      </div>

      <LoginForm
        v-if="mode === 'login'"
        :allow-registration="allowRegistration"
        @switchToRegister="mode = 'register'"
      />
      <RegisterForm
        v-else
        @switchToLogin="mode = 'login'"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { FileSpreadsheet } from 'lucide-vue-next'
import LoginForm from './auth/LoginForm.vue'
import RegisterForm from './auth/RegisterForm.vue'
import { getAuthConfig } from '../api'

const mode = ref('login')
const allowRegistration = ref(false)

onMounted(async () => {
  try {
    const cfg = await getAuthConfig()
    allowRegistration.value = cfg.allow_registration
  } catch {
    allowRegistration.value = false
  }
})
</script>

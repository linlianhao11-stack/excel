<template>
  <section class="space-y-5">
    <div class="flex items-center gap-2">
      <Users class="w-[18px] h-[18px]" :style="{ color: 'var(--primary)' }" />
      <h2 class="text-base font-semibold" :style="{ color: 'var(--text)' }">用户管理</h2>
      <span
        class="text-[11px] font-medium px-2 py-0.5 rounded"
        :style="{ background: 'var(--primary-muted)', color: 'var(--primary)' }"
      >仅管理员</span>
    </div>

    <!-- 用户列表 -->
    <div class="space-y-1 max-w-md">
      <UserListRow
        v-for="u in users"
        :key="u.id"
        :user="u"
        :current-user-id="currentUserId"
        @resetPassword="onResetPassword"
        @toggleActive="handleToggleActive"
        @deleteUser="(id) => $emit('deleteUser', id)"
      />
    </div>

    <!-- 添加用户 -->
    <div class="flex gap-2 max-w-md">
      <input
        v-model="newUsername"
        placeholder="用户名"
        class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none border"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
      />
      <input
        v-model="newPassword"
        type="password"
        placeholder="密码"
        class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none border"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
      />
      <button
        @click="handleAdd"
        :disabled="!newUsername || !newPassword"
        class="px-4 py-2.5 text-[14px] font-medium text-white rounded-lg disabled:opacity-50 transition-colors"
        :style="{ background: 'var(--text)' }"
      >添加</button>
    </div>

    <div v-if="error || localError" class="text-[13px]" :style="{ color: 'var(--error-emphasis)' }">
      {{ error || localError }}
    </div>

    <!-- 重置密码弹窗 -->
    <AdminResetPasswordModal
      v-if="resetTarget"
      :username="resetTarget.username"
      :loading="resetLoading"
      :api-error="resetApiError"
      @confirm="handleResetConfirm"
      @cancel="closeResetModal"
    />
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { Users } from 'lucide-vue-next'
import UserListRow from './UserListRow.vue'
import AdminResetPasswordModal from './AdminResetPasswordModal.vue'
import { adminResetPassword, setUserActive } from '../../api'

defineProps({
  users: { type: Array, default: () => [] },
  currentUserId: { type: [String, Number], default: null },
  error: { type: String, default: '' }
})

const emit = defineEmits(['addUser', 'deleteUser', 'refresh'])

const newUsername = ref('')
const newPassword = ref('')
const resetTarget = ref(null)
const resetLoading = ref(false)
const resetApiError = ref('')
const localError = ref('')

function handleAdd() {
  emit('addUser', { username: newUsername.value, password: newPassword.value })
  newUsername.value = ''
  newPassword.value = ''
}

function onResetPassword(user) {
  resetApiError.value = ''
  resetTarget.value = user
}

function closeResetModal() {
  resetTarget.value = null
  resetApiError.value = ''
}

async function handleResetConfirm(newPw) {
  resetApiError.value = ''
  resetLoading.value = true
  try {
    await adminResetPassword(resetTarget.value.id, newPw)
    resetTarget.value = null
  } catch (e) {
    resetApiError.value = e.response?.data?.detail || '重置密码失败'
  } finally {
    resetLoading.value = false
  }
}

async function handleToggleActive(user) {
  // UserListRow emit 传入整个 user 对象；toggle 即取反
  localError.value = ''
  try {
    await setUserActive(user.id, !user.is_active)
    emit('refresh')
  } catch (e) {
    localError.value = e.response?.data?.detail || '操作失败'
  }
}
</script>

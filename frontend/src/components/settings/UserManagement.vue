<template>
  <section class="space-y-5">
    <div class="flex items-center gap-2">
      <Users class="w-[18px] h-[18px]" style="color: var(--primary)" />
      <h2 class="text-base font-semibold" style="color: var(--text)">用户管理</h2>
      <span
        class="text-[11px] font-medium px-2 py-0.5 rounded"
        :style="{ background: 'var(--primary-muted)', color: 'var(--primary)' }"
      >仅管理员</span>
    </div>

    <!-- 用户列表 -->
    <div class="space-y-1 max-w-md">
      <div
        v-for="u in users"
        :key="u.id"
        class="flex items-center gap-2 px-3.5 py-2.5 rounded-lg text-[14px]"
        style="background: var(--background)"
      >
        <span class="flex-1" style="color: var(--text)">{{ u.username }}</span>
        <span
          v-if="u.is_admin"
          class="text-[11px] font-medium px-2 py-0.5 rounded"
          :style="{ background: 'var(--warning-subtle)', color: 'var(--warning-emphasis)' }"
        >管理员</span>
        <button
          v-if="u.id !== currentUserId"
          @click="$emit('deleteUser', u.id)"
          style="color: var(--text-placeholder)"
        >
          <Trash2 class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>

    <!-- 添加用户 -->
    <div class="flex gap-2 max-w-md">
      <input
        v-model="newUsername"
        placeholder="用户名"
        class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
        :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
      />
      <input
        v-model="newPassword"
        type="password"
        placeholder="密码"
        class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
        :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
      />
      <button
        @click="handleAdd"
        :disabled="!newUsername || !newPassword"
        class="px-4 py-2.5 text-[14px] font-medium text-white rounded-lg disabled:opacity-50 transition-colors"
        style="background: var(--text)"
      >
        添加
      </button>
    </div>
    <div v-if="error" class="text-[13px]" style="color: var(--error-emphasis)">{{ error }}</div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { Users, Trash2 } from 'lucide-vue-next'

defineProps({
  users: { type: Array, default: () => [] },
  currentUserId: { type: [String, Number], default: null },
  error: { type: String, default: '' }
})

const emit = defineEmits(['addUser', 'deleteUser'])

const newUsername = ref('')
const newPassword = ref('')

function handleAdd() {
  emit('addUser', { username: newUsername.value, password: newPassword.value })
  newUsername.value = ''
  newPassword.value = ''
}
</script>

<template>
  <section class="space-y-5">
    <div class="flex items-center gap-2">
      <Lock class="w-[18px] h-[18px]" style="color: var(--primary)" />
      <h2 class="text-base font-semibold" style="color: var(--text)">修改密码</h2>
    </div>
    <div class="space-y-4 max-w-md">
      <div>
        <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">当前密码</label>
        <input
          v-model="oldPw"
          type="password"
          placeholder="输入当前密码"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
          :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        />
      </div>
      <div>
        <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">新密码</label>
        <input
          v-model="newPw"
          type="password"
          placeholder="输入新密码"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
          :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        />
      </div>
      <div class="flex items-center gap-3">
        <button
          @click="handleSubmit"
          :disabled="!oldPw || !newPw"
          class="px-5 py-2.5 text-[14px] font-medium text-white rounded-[10px] disabled:opacity-50 transition-colors"
          style="background: var(--text)"
        >
          修改密码
        </button>
        <span v-if="success" class="text-[13px]" style="color: var(--success-emphasis)">修改成功</span>
        <span v-if="error" class="text-[13px]" style="color: var(--error-emphasis)">{{ error }}</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { Lock } from 'lucide-vue-next'

defineProps({
  success: Boolean,
  error: String,
})

const emit = defineEmits(['changePassword'])

const oldPw = ref('')
const newPw = ref('')

function handleSubmit() {
  emit('changePassword', { oldPassword: oldPw.value, newPassword: newPw.value })
  oldPw.value = ''
  newPw.value = ''
}
</script>

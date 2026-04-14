<template>
  <section class="space-y-5">
    <div class="flex items-center gap-2">
      <Bot class="w-[18px] h-[18px]" style="color: var(--primary)" />
      <h2 class="text-base font-semibold" style="color: var(--text)">AI 模型</h2>
    </div>
    <div class="space-y-4 max-w-md">
      <div>
        <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">服务商</label>
        <select
          :value="provider"
          @change="$emit('update:provider', $event.target.value)"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
          :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        >
          <option value="deepseek">DeepSeek</option>
          <option value="aliyun">阿里云（通义千问）</option>
        </select>
      </div>
      <div>
        <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">API Key</label>
        <div class="flex gap-2">
          <input
            :value="apiKey"
            @input="$emit('update:apiKey', $event.target.value)"
            :type="showKey ? 'text' : 'password'"
            :placeholder="apiKeyMasked || '请输入 API Key'"
            class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
            :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
          />
          <button
            @click="showKey = !showKey"
            class="px-2.5 rounded-lg transition-colors"
            :style="{ border: '1px solid var(--border)', color: 'var(--text-muted)' }"
          >
            <component :is="showKey ? EyeOff : Eye" class="w-4 h-4" />
          </button>
        </div>
      </div>
      <div>
        <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">Base URL</label>
        <input
          :value="baseUrl"
          @input="$emit('update:baseUrl', $event.target.value)"
          :placeholder="defaultBaseUrl"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
          :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        />
      </div>
      <div>
        <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">模型</label>
        <select
          :value="model"
          @change="$emit('update:model', $event.target.value)"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none"
          :style="{ border: '1px solid var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        >
          <option v-for="m in modelList" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
      <div class="flex items-center gap-3">
        <button
          @click="$emit('save')"
          :disabled="saving"
          class="px-5 py-2.5 text-[14px] font-medium rounded-[10px] text-white disabled:opacity-50 transition-colors"
          style="background: var(--primary)"
        >
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <span v-if="saveSuccess" class="text-[13px]" style="color: var(--success-emphasis)">已保存</span>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { Bot, Eye, EyeOff } from 'lucide-vue-next'

const showKey = ref(false)

defineProps({
  provider: String,
  apiKey: String,
  apiKeyMasked: String,
  baseUrl: String,
  defaultBaseUrl: String,
  model: String,
  modelList: { type: Array, default: () => [] },
  saving: Boolean,
  saveSuccess: Boolean,
})

defineEmits(['update:provider', 'update:apiKey', 'update:baseUrl', 'update:model', 'save'])
</script>

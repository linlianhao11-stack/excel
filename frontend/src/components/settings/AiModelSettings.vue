<template>
  <section class="space-y-5">
    <div class="flex items-center gap-2">
      <Bot class="w-[18px] h-[18px]" style="color: var(--primary)" />
      <h2 class="text-base font-semibold" style="color: var(--text)">AI 模型</h2>
    </div>
    <div class="space-y-4 max-w-md">
      <!-- 服务商 -->
      <div>
        <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">服务商</label>
        <AppSelect
          :modelValue="provider"
          @update:modelValue="$emit('update:provider', $event)"
          :options="providerOptions"
          placeholder="选择服务商"
        />
      </div>

      <!-- API Key -->
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

      <!-- Base URL -->
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

      <!-- 模型 -->
      <div>
        <label class="block text-[13px] font-medium mb-1.5" style="color: var(--text-secondary)">模型</label>
        <AppSelect
          :modelValue="model"
          @update:modelValue="$emit('update:model', $event)"
          :options="modelList"
          placeholder="选择模型"
        />
      </div>

      <!-- 操作按钮 -->
      <div class="flex items-center gap-3">
        <button
          @click="$emit('save')"
          :disabled="saving"
          class="px-5 py-2.5 text-[14px] font-medium rounded-[10px] text-white disabled:opacity-50 transition-colors cursor-pointer"
          style="background: var(--primary)"
        >
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <button
          @click="handleTest"
          :disabled="testing"
          class="px-5 py-2.5 text-[14px] font-medium rounded-[10px] transition-colors cursor-pointer disabled:opacity-50"
          :style="{
            border: '1px solid var(--border)',
            color: 'var(--text-secondary)',
            background: 'var(--surface)'
          }"
        >
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
        <span v-if="saveSuccess" class="text-[13px]" style="color: var(--success-emphasis)">已保存</span>
      </div>

      <!-- 测试结果 -->
      <div
        v-if="testResult"
        class="flex items-center gap-2 px-4 py-3 rounded-lg text-[13px]"
        :style="{
          background: testResult.ok ? 'var(--success-subtle)' : 'var(--error-subtle)',
          color: testResult.ok ? 'var(--success-emphasis)' : 'var(--error-emphasis)',
        }"
      >
        <component :is="testResult.ok ? CircleCheck : CircleX" class="w-4 h-4 shrink-0" />
        {{ testResult.message }}
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { Bot, Eye, EyeOff, CircleCheck, CircleX } from 'lucide-vue-next'
import { testConnection } from '../../api'
import AppSelect from '../common/AppSelect.vue'

const showKey = ref(false)
const testing = ref(false)
const testResult = ref(null)

const providerOptions = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'aliyun', label: '阿里云（通义千问）' },
]

const props = defineProps({
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

async function handleTest() {
  testing.value = true
  testResult.value = null
  try {
    const result = await testConnection(props.provider, props.apiKey, props.model, props.baseUrl)
    testResult.value = result
  } catch (e) {
    testResult.value = { ok: false, message: e.response?.data?.detail || '测试请求失败' }
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0 relative">
    <TopControls @newChat="$emit('newChat')" />

    <div class="flex-1 overflow-y-auto">
      <!-- 窄列：常规设置 -->
      <div class="max-w-xl px-6 pt-14 mx-auto space-y-8">
        <div>
          <h1 class="text-2xl font-semibold" style="color: var(--text)">设置</h1>
          <p class="text-[14px] mt-1" style="color: var(--text-muted)">
            管理 AI 模型配置、用户账号和安全设置
          </p>
        </div>

        <div class="h-px" style="background: var(--border)" />

        <AiModelSettings
          :provider="provider"
          :apiKey="apiKey"
          :apiKeyMasked="apiKeyMasked"
          :baseUrl="baseUrl"
          :defaultBaseUrl="currentProviderBaseUrl"
          :model="model"
          :modelList="currentModelList"
          :saving="saving"
          :saveSuccess="saveSuccess"
          @update:provider="onProviderChange"
          @update:apiKey="apiKey = $event"
          @update:baseUrl="baseUrl = $event"
          @update:model="model = $event"
          @save="saveSettings"
        />

        <div class="h-px" style="background: var(--border)" />

        <RegistrationToggle
          v-if="isAdmin"
          :modelValue="allowRegistration"
          @update:modelValue="handleToggleRegistration"
        />
        <div
          v-if="isAdmin && toggleError"
          class="text-[13px]"
          :style="{ color: 'var(--error-emphasis)' }"
        >{{ toggleError }}</div>
        <div v-if="isAdmin" class="h-px" style="background: var(--border)" />

        <UserManagement
          v-if="isAdmin"
          :users="userList"
          :currentUserId="currentUser?.id"
          :error="userError"
          @addUser="handleAddUser"
          @deleteUser="handleDeleteUser"
          @refresh="loadUsers"
        />

        <div v-if="isAdmin" class="h-px" style="background: var(--border)" />

        <ChangePassword
          :success="pwSuccess"
          :error="pwError"
          @changePassword="handleChangePassword"
        />
      </div>

      <!-- 宽列：管理员全局对话表格，放最底部 -->
      <div v-if="isAdmin" class="max-w-5xl px-6 py-14 mx-auto">
        <AdminConversationsPanel />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuth } from '../composables/useAuth'
import TopControls from './layout/TopControls.vue'
import AiModelSettings from './settings/AiModelSettings.vue'
import UserManagement from './settings/UserManagement.vue'
import ChangePassword from './settings/ChangePassword.vue'
import RegistrationToggle from './settings/RegistrationToggle.vue'
import AdminConversationsPanel from './settings/AdminConversationsPanel.vue'
import {
  getSettings, updateSettings,
  listUsers, createUser, deleteUser, changePassword,
  getAuthConfig, setAuthConfig,
} from '../api'

defineEmits(['newChat'])

const { user: currentUser, isAdmin } = useAuth()

const provider = ref('deepseek')
const providers = ref({})
const apiKey = ref('')
const apiKeyMasked = ref('')
const baseUrl = ref('')
const model = ref('')
const saving = ref(false)
const saveSuccess = ref(false)

const currentModelList = computed(() => providers.value[provider.value]?.models || [])
const currentProviderBaseUrl = computed(() => providers.value[provider.value]?.default_base_url || '')

function onProviderChange(val) {
  provider.value = val
  const cfg = providers.value[val]
  if (cfg) {
    baseUrl.value = cfg.default_base_url
    model.value = cfg.models[0] || ''
  }
  apiKey.value = ''
  apiKeyMasked.value = ''
}

const userList = ref([])
const userError = ref('')
const pwSuccess = ref(false)
const pwError = ref('')
const allowRegistration = ref(true)
const toggleError = ref('')

async function loadSettings() {
  try {
    const data = await getSettings()
    provider.value = data.provider || 'deepseek'
    providers.value = data.providers || {}
    apiKeyMasked.value = data.api_key_masked
    baseUrl.value = data.base_url
    model.value = data.model
  } catch { /* 静默处理 */ }
}

async function saveSettings() {
  saving.value = true
  saveSuccess.value = false
  try {
    const updates = { provider: provider.value, base_url: baseUrl.value, model: model.value }
    if (apiKey.value) updates.api_key = apiKey.value
    await updateSettings(updates)
    saveSuccess.value = true
    apiKey.value = ''
    await loadSettings()
    setTimeout(() => (saveSuccess.value = false), 2000)
  } finally {
    saving.value = false
  }
}

async function loadUsers() {
  if (!isAdmin.value) return
  try {
    userList.value = await listUsers()
  } catch { /* 静默处理 */ }
}

async function handleAddUser({ username, password }) {
  userError.value = ''
  try {
    await createUser(username, password, false)
    await loadUsers()
  } catch (e) {
    userError.value = e.response?.data?.detail || '添加失败'
  }
}

async function handleDeleteUser(userId) {
  await deleteUser(userId)
  await loadUsers()
}

async function loadAuthConfig() {
  if (!isAdmin.value) return
  try {
    const cfg = await getAuthConfig()
    allowRegistration.value = cfg.allow_registration
  } catch { /* 静默 */ }
}

async function handleToggleRegistration(val) {
  toggleError.value = ''
  try {
    await setAuthConfig(val)
    allowRegistration.value = val
  } catch (e) {
    toggleError.value = e.response?.data?.detail || '切换注册开关失败'
  }
}

async function handleChangePassword({ oldPassword, newPassword }) {
  pwError.value = ''
  pwSuccess.value = false
  try {
    await changePassword(oldPassword, newPassword)
    pwSuccess.value = true
    setTimeout(() => (pwSuccess.value = false), 2000)
  } catch (e) {
    pwError.value = e.response?.data?.detail || '修改失败'
  }
}

onMounted(() => {
  loadSettings()
  loadUsers()
  loadAuthConfig()
})
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="$emit('close')">
    <div class="bg-white rounded-2xl w-full max-w-lg mx-4 shadow-xl max-h-[80vh] overflow-y-auto">
      <!-- 头部 -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-[#e5e5e5]">
        <h2 class="text-lg font-semibold text-[#1a1a1a]">设置</h2>
        <button @click="$emit('close')" class="p-1 text-[#999] hover:text-[#555] rounded-md hover:bg-[#f4f4f4]">
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 space-y-6">
        <!-- AI 模型设置 -->
        <section>
          <h3 class="text-sm font-semibold text-[#1a1a1a] mb-3 flex items-center gap-2">
            <Bot class="w-4 h-4" /> AI 模型
          </h3>
          <div class="space-y-3">
            <div>
              <label class="block text-xs text-[#999] mb-1">服务商</label>
              <select
                v-model="provider"
                @change="onProviderChange"
                class="w-full px-3 py-2 border border-[#d9d9d9] rounded-lg text-sm focus:outline-none focus:border-[#999] bg-white"
              >
                <option value="deepseek">DeepSeek</option>
                <option value="aliyun">阿里云（通义千问）</option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-[#999] mb-1">API Key</label>
              <div class="flex gap-2">
                <input
                  v-model="apiKey"
                  :type="showKey ? 'text' : 'password'"
                  :placeholder="apiKeyMasked || '请输入 API Key'"
                  class="flex-1 px-3 py-2 border border-[#d9d9d9] rounded-lg text-sm focus:outline-none focus:border-[#999]"
                />
                <button @click="showKey = !showKey" class="px-2 text-[#999] hover:text-[#555]">
                  <component :is="showKey ? EyeOff : Eye" class="w-4 h-4" />
                </button>
              </div>
            </div>
            <div>
              <label class="block text-xs text-[#999] mb-1">Base URL</label>
              <input
                v-model="baseUrl"
                :placeholder="currentProviderBaseUrl"
                class="w-full px-3 py-2 border border-[#d9d9d9] rounded-lg text-sm focus:outline-none focus:border-[#999]"
              />
            </div>
            <div>
              <label class="block text-xs text-[#999] mb-1">模型</label>
              <select
                v-model="model"
                class="w-full px-3 py-2 border border-[#d9d9d9] rounded-lg text-sm focus:outline-none focus:border-[#999] bg-white"
              >
                <option v-for="m in currentModelList" :key="m" :value="m">{{ m }}</option>
              </select>
            </div>
            <button
              @click="saveSettings"
              :disabled="saving"
              class="px-4 py-2 bg-[#1a1a1a] text-white text-sm rounded-lg hover:bg-[#333] disabled:opacity-50"
            >
              {{ saving ? '保存中...' : '保存' }}
            </button>
            <span v-if="saveSuccess" class="text-green-600 text-sm ml-2">已保存</span>
          </div>
        </section>

        <!-- 用户管理（仅管理员） -->
        <section v-if="isAdmin">
          <h3 class="text-sm font-semibold text-[#1a1a1a] mb-3 flex items-center gap-2">
            <Users class="w-4 h-4" /> 用户管理
          </h3>
          <div class="space-y-2 mb-3">
            <div
              v-for="u in userList"
              :key="u.id"
              class="flex items-center gap-2 px-3 py-2 bg-[#f9f9f9] rounded-lg text-sm"
            >
              <span class="flex-1">{{ u.username }}</span>
              <span v-if="u.is_admin" class="text-xs text-orange-500 font-medium">管理员</span>
              <button
                v-if="u.id !== currentUser?.id"
                @click="handleDeleteUser(u.id)"
                class="text-[#999] hover:text-red-500"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- 添加用户 -->
          <div class="flex gap-2">
            <input
              v-model="newUsername"
              placeholder="用户名"
              class="flex-1 px-3 py-2 border border-[#d9d9d9] rounded-lg text-sm focus:outline-none focus:border-[#999]"
            />
            <input
              v-model="newPassword"
              type="password"
              placeholder="密码"
              class="flex-1 px-3 py-2 border border-[#d9d9d9] rounded-lg text-sm focus:outline-none focus:border-[#999]"
            />
            <button
              @click="handleAddUser"
              :disabled="!newUsername || !newPassword"
              class="px-3 py-2 bg-[#1a1a1a] text-white text-sm rounded-lg hover:bg-[#333] disabled:opacity-50"
            >
              添加
            </button>
          </div>
          <div v-if="userError" class="mt-2 text-red-500 text-sm">{{ userError }}</div>
        </section>

        <!-- 修改密码 -->
        <section>
          <h3 class="text-sm font-semibold text-[#1a1a1a] mb-3 flex items-center gap-2">
            <Lock class="w-4 h-4" /> 修改密码
          </h3>
          <div class="space-y-3">
            <input
              v-model="oldPw"
              type="password"
              placeholder="当前密码"
              class="w-full px-3 py-2 border border-[#d9d9d9] rounded-lg text-sm focus:outline-none focus:border-[#999]"
            />
            <input
              v-model="newPw"
              type="password"
              placeholder="新密码"
              class="w-full px-3 py-2 border border-[#d9d9d9] rounded-lg text-sm focus:outline-none focus:border-[#999]"
            />
            <button
              @click="handleChangePassword"
              :disabled="!oldPw || !newPw"
              class="px-4 py-2 bg-[#1a1a1a] text-white text-sm rounded-lg hover:bg-[#333] disabled:opacity-50"
            >
              修改密码
            </button>
            <span v-if="pwSuccess" class="text-green-600 text-sm ml-2">修改成功</span>
            <span v-if="pwError" class="text-red-500 text-sm ml-2">{{ pwError }}</span>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { X, Bot, Users, Trash2, Eye, EyeOff, Lock } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'
import {
  getSettings, updateSettings,
  listUsers, createUser, deleteUser, changePassword
} from '../api'

defineEmits(['close'])

const { user: currentUser, isAdmin } = useAuth()

// AI 设置
const provider = ref('deepseek')
const providers = ref({})
const apiKey = ref('')
const apiKeyMasked = ref('')
const baseUrl = ref('')
const model = ref('')
const showKey = ref(false)
const saving = ref(false)
const saveSuccess = ref(false)

const currentModelList = computed(() => providers.value[provider.value]?.models || [])
const currentProviderBaseUrl = computed(() => providers.value[provider.value]?.default_base_url || '')

function onProviderChange() {
  const cfg = providers.value[provider.value]
  if (cfg) {
    baseUrl.value = cfg.default_base_url
    model.value = cfg.models[0] || ''
  }
  apiKey.value = ''
  apiKeyMasked.value = ''
}

// 用户管理
const userList = ref([])
const newUsername = ref('')
const newPassword = ref('')
const userError = ref('')

// 修改密码
const oldPw = ref('')
const newPw = ref('')
const pwSuccess = ref(false)
const pwError = ref('')

async function loadSettings() {
  try {
    const data = await getSettings()
    provider.value = data.provider || 'deepseek'
    providers.value = data.providers || {}
    apiKeyMasked.value = data.api_key_masked
    baseUrl.value = data.base_url
    model.value = data.model
  } catch {}
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
    setTimeout(() => saveSuccess.value = false, 2000)
  } finally {
    saving.value = false
  }
}

async function loadUsers() {
  if (!isAdmin.value) return
  try {
    userList.value = await listUsers()
  } catch {}
}

async function handleAddUser() {
  userError.value = ''
  try {
    await createUser(newUsername.value, newPassword.value, false)
    newUsername.value = ''
    newPassword.value = ''
    await loadUsers()
  } catch (e) {
    userError.value = e.response?.data?.detail || '添加失败'
  }
}

async function handleDeleteUser(userId) {
  await deleteUser(userId)
  await loadUsers()
}

async function handleChangePassword() {
  pwError.value = ''
  pwSuccess.value = false
  try {
    await changePassword(oldPw.value, newPw.value)
    oldPw.value = ''
    newPw.value = ''
    pwSuccess.value = true
    setTimeout(() => pwSuccess.value = false, 2000)
  } catch (e) {
    pwError.value = e.response?.data?.detail || '修改失败'
  }
}

onMounted(() => {
  loadSettings()
  loadUsers()
})
</script>

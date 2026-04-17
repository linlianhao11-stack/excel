import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

function decodeExp(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp || 0
  } catch { return 0 }
}

function updateTokenIfNewer(newToken) {
  if (!newToken) return
  const cur = localStorage.getItem('token')
  if (!cur || decodeExp(newToken) > decodeExp(cur)) {
    localStorage.setItem('token', newToken)
  }
}

// 自动附加 JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：滑动刷新 token + 401 跳登录
api.interceptors.response.use(
  (res) => {
    const newToken = res.headers['x-new-token']
    if (newToken) updateTokenIfNewer(newToken)
    return res
  },
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

export async function uploadFiles(files) {
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))
  const { data } = await api.post('/files/upload', formData)
  return data.files
}

export async function listFiles() {
  const { data } = await api.get('/files/list')
  return data.files
}

export async function deleteFile(fileId) {
  await api.delete(`/files/${fileId}`)
}

export async function getExcelPreview(fileId) {
  const { data } = await api.get(`/files/${fileId}/preview`)
  return data.sheets
}

export async function getOutputPreview(filename) {
  const { data } = await api.get('/files/preview-output', { params: { filename } })
  return data.sheets
}

export function chatStream(message, fileIds, conversationId, onEvent, imageIds = []) {
  const controller = new AbortController()
  const token = localStorage.getItem('token')

  fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ message, file_ids: fileIds, image_ids: imageIds, conversation_id: conversationId }),
    signal: controller.signal,
  }).then(async (response) => {
    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.reload()
      return
    }
    // 读滑动刷新的新 token
    const _newToken = response.headers.get('X-New-Token')
    if (_newToken) updateTokenIfNewer(_newToken)
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            onEvent({ type: 'stream_end' })
            return
          }
          try {
            onEvent(JSON.parse(data))
          } catch { /* ignore */ }
        }
      }
    }
  }).catch(err => {
    if (err.name !== 'AbortError') {
      onEvent({ type: 'error', message: err.message })
    }
  })

  return controller
}

export async function downloadFile(path) {
  const filename = path.split('/').pop()
  const token = localStorage.getItem('token')
  const response = await fetch(`/api/download?filename=${encodeURIComponent(filename)}&token=${encodeURIComponent(token)}`)
  if (!response.ok) throw new Error('下载失败')
  const blob = await response.blob()
  const reader = new FileReader()
  reader.onload = () => {
    const a = document.createElement('a')
    a.href = reader.result
    a.download = filename
    a.click()
  }
  reader.readAsDataURL(blob)
}

// Conversations API
export async function listConversations() {
  const { data } = await api.get('/conversations')
  return data.conversations
}

export async function createConversation() {
  const { data } = await api.post('/conversations')
  return data
}

export async function getConversationMessages(convId) {
  const { data } = await api.get(`/conversations/${convId}/messages`)
  return data
}

export async function deleteConversation(convId) {
  await api.delete(`/conversations/${convId}`)
}

// Settings API
export async function getSettings() {
  const { data } = await api.get('/settings')
  return data
}

export async function updateSettings(settings) {
  const { data } = await api.put('/settings', settings)
  return data
}

export async function testConnection(provider, apiKey, model, baseUrl) {
  const { data } = await api.post('/settings/test', { provider, api_key: apiKey, model, base_url: baseUrl })
  return data
}

// User management API
export async function listUsers() {
  const { data } = await api.get('/auth/users')
  return data.users
}

export async function createUser(username, password, isAdmin) {
  const { data } = await api.post('/auth/users', { username, password, is_admin: isAdmin })
  return data
}

export async function deleteUser(userId) {
  await api.delete(`/auth/users/${userId}`)
}

export async function changePassword(oldPassword, newPassword) {
  const { data } = await api.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword })
  return data
}

// Diff Review API
export async function approveDiff(conversationId) {
  const { data } = await api.post('/diff/approve', { conversation_id: conversationId })
  return data
}

export function rejectDiffStream(conversationId, reasonType, reasonText, onEvent) {
  const controller = new AbortController()
  const token = localStorage.getItem('token')

  fetch('/api/diff/reject', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      reason_type: reasonType,
      reason_text: reasonText,
    }),
    signal: controller.signal,
  }).then(async (response) => {
    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.reload()
      return
    }
    // 读滑动刷新的新 token
    const _newToken = response.headers.get('X-New-Token')
    if (_newToken) updateTokenIfNewer(_newToken)
    // 非 SSE 响应（如超限错误），直接解析 JSON
    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      const data = await response.json()
      if (data.error) {
        onEvent({ type: 'error', message: data.error })
      }
      onEvent({ type: 'stream_end' })
      return
    }
    // SSE 流
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            onEvent({ type: 'stream_end' })
            return
          }
          try { onEvent(JSON.parse(data)) } catch { /* ignore */ }
        }
      }
    }
  }).catch(err => {
    if (err.name !== 'AbortError') {
      onEvent({ type: 'error', message: err.message })
    }
  })

  return controller
}

// 认证配置
export async function getAuthConfig() {
  const { data } = await api.get('/auth/config')
  return data
}

export async function setAuthConfig(allowRegistration) {
  const { data } = await api.put('/auth/config', { allow_registration: allowRegistration })
  return data
}

// 自注册
export async function registerUser(username, password) {
  const { data } = await api.post('/auth/register', { username, password })
  return data
}

// 管理员重置他人密码
export async function adminResetPassword(userId, newPassword) {
  const { data } = await api.post(`/auth/users/${userId}/reset-password`, { new_password: newPassword })
  return data
}

// 启用/禁用账号
export async function setUserActive(userId, isActive) {
  const { data } = await api.patch(`/auth/users/${userId}/active`, { is_active: isActive })
  return data
}

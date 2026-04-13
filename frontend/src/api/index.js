import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 自动附加 JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 时自动跳转登录
api.interceptors.response.use(
  (res) => res,
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

export function chatStream(message, fileIds, conversationId, onEvent) {
  const controller = new AbortController()
  const token = localStorage.getItem('token')

  fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ message, file_ids: fileIds, conversation_id: conversationId }),
    signal: controller.signal,
  }).then(async (response) => {
    if (response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.reload()
      return
    }
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

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

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

export function chatStream(message, fileIds, onEvent) {
  const controller = new AbortController()

  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, file_ids: fileIds }),
    signal: controller.signal,
  }).then(async (response) => {
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
          } catch { /* ignore parse errors */ }
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

export function getDownloadUrl(path) {
  return `/api/download?path=${encodeURIComponent(path)}`
}

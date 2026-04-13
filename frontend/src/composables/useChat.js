import { ref, reactive } from 'vue'
import { chatStream } from '../api'

const messages = ref([])
const streaming = ref(false)
const status = ref(null) // null | 'thinking' | 'running' | 'verifying' | 'reporting'
let controller = null

export function useChat() {
  function send(text, fileIds, conversationId, imageIds = []) {
    const userMsg = { id: Date.now(), role: 'user', content: text }
    if (imageIds.length > 0) {
      const token = localStorage.getItem('token')
      userMsg.images = imageIds.map(id => `/api/files/${id}/image?token=${encodeURIComponent(token)}`)
    }
    messages.value.push(userMsg)

    const assistantMsg = reactive({
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      toolCalls: [],
      outputPath: null,
      error: null,
    })
    messages.value.push(assistantMsg)

    streaming.value = true
    status.value = 'thinking'

    controller = chatStream(
      text, fileIds, conversationId,
      (event) => {
        switch (event.type) {
          case 'text':
            status.value = null
            assistantMsg.content += event.content
            break
          case 'tool_call':
            status.value = 'running'
            assistantMsg.toolCalls.push(reactive({
              name: event.name,
              code: event.code,
              result: null,
              expanded: false,
            }))
            break
          case 'tool_result': {
            status.value = 'thinking'
            const lastCall = assistantMsg.toolCalls[assistantMsg.toolCalls.length - 1]
            if (lastCall) lastCall.result = event.result
            break
          }
          case 'phase':
            status.value = event.name // 'verifying' | 'reporting'
            break
          case 'output_ready':
            assistantMsg.outputPath = event.output_path
            break
          case 'done':
            status.value = null
            assistantMsg.outputPath = event.output_path || assistantMsg.outputPath
            streaming.value = false
            break
          case 'error':
            status.value = null
            assistantMsg.error = event.message
            streaming.value = false
            break
          case 'stream_end':
            status.value = null
            streaming.value = false
            break
        }
      },
      imageIds,
    )
  }

  function stop() {
    if (controller) controller.abort()
    streaming.value = false
    status.value = null
  }

  function clearMessages() {
    messages.value = []
    status.value = null
  }

  function loadFromHistory(historyMessages) {
    messages.value = historyMessages.map((m, i) => ({
      id: m.id || Date.now() + i,
      role: m.role,
      content: m.content || '',
      toolCalls: (m.tool_calls || []).map(tc => reactive({
        name: tc.name,
        code: tc.code,
        result: tc.result || null,
        expanded: false,
      })),
      outputPath: m.output_path || null,
      error: m.error || null,
    }))
  }

  return { messages, streaming, status, send, stop, clearMessages, loadFromHistory }
}

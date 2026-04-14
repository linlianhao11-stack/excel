import { ref, reactive } from 'vue'
import { chatStream, rejectDiffStream } from '../api'

const messages = ref([])
const streaming = ref(false)
const status = ref(null) // null | 'thinking' | 'running' | 'verifying' | 'reporting' | 'reviewing'
let controller = null

function _handleEvent(assistantMsg, event, conversationId) {
  switch (event.type) {
    case 'text':
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
    case 'diff_review':
      status.value = 'reviewing'
      assistantMsg.diff = event.diff
      assistantMsg.conversationId = conversationId
      break
    case 'create_summary':
      assistantMsg.createSummary = event.summary
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
}

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
      diff: null,
      createSummary: null,
      conversationId: null,
    })
    messages.value.push(assistantMsg)

    streaming.value = true
    status.value = 'thinking'

    controller = chatStream(
      text, fileIds, conversationId,
      (event) => _handleEvent(assistantMsg, event, conversationId),
      imageIds,
    )
  }

  function retryFromReject(conversationId, reasonType, reasonText) {
    const assistantMsg = reactive({
      id: Date.now(),
      role: 'assistant',
      content: '',
      toolCalls: [],
      outputPath: null,
      error: null,
      diff: null,
      createSummary: null,
      conversationId: null,
    })
    messages.value.push(assistantMsg)

    streaming.value = true
    status.value = 'thinking'

    controller = rejectDiffStream(
      conversationId, reasonType, reasonText,
      (event) => _handleEvent(assistantMsg, event, conversationId),
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
      diff: null,
      createSummary: null,
      conversationId: null,
    }))
  }

  return { messages, streaming, status, send, retryFromReject, stop, clearMessages, loadFromHistory }
}

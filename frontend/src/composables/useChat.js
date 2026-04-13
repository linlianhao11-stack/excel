import { ref, reactive } from 'vue'
import { chatStream } from '../api'

const messages = ref([])
const streaming = ref(false)
let controller = null

export function useChat() {
  function send(text, fileIds, conversationId) {
    messages.value.push({ id: Date.now(), role: 'user', content: text })

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

    controller = chatStream(text, fileIds, conversationId, (event) => {
      switch (event.type) {
        case 'text':
          assistantMsg.content += event.content
          break
        case 'tool_call':
          assistantMsg.toolCalls.push(reactive({
            name: event.name,
            code: event.code,
            result: null,
            expanded: false,
          }))
          break
        case 'tool_result': {
          const lastCall = assistantMsg.toolCalls[assistantMsg.toolCalls.length - 1]
          if (lastCall) lastCall.result = event.result
          break
        }
        case 'done':
          assistantMsg.outputPath = event.output_path
          streaming.value = false
          break
        case 'error':
          assistantMsg.error = event.message
          streaming.value = false
          break
        case 'stream_end':
          streaming.value = false
          break
      }
    })
  }

  function stop() {
    if (controller) controller.abort()
    streaming.value = false
  }

  function clearMessages() {
    messages.value = []
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

  return { messages, streaming, send, stop, clearMessages, loadFromHistory }
}

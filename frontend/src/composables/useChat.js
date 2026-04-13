import { ref, reactive } from 'vue'
import { chatStream } from '../api'

const messages = ref([])
const streaming = ref(false)

export function useChat() {
  let controller = null

  function send(text, fileIds) {
    messages.value.push({ role: 'user', content: text })

    const assistantMsg = reactive({
      role: 'assistant',
      content: '',
      toolCalls: [],
      outputPath: null,
      error: null,
    })
    messages.value.push(assistantMsg)

    streaming.value = true

    controller = chatStream(text, fileIds, (event) => {
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

  return { messages, streaming, send, stop, clearMessages }
}

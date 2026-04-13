import { ref } from 'vue'
import { listConversations, createConversation, deleteConversation, getConversationMessages } from '../api'

const conversations = ref([])
const currentConvId = ref(null)
const loading = ref(false)

export function useConversations() {
  async function load() {
    loading.value = true
    try {
      conversations.value = await listConversations()
    } catch {
      conversations.value = []
    } finally {
      loading.value = false
    }
  }

  async function create() {
    const data = await createConversation()
    conversations.value.unshift({ id: data.id, title: data.title, created_at: new Date().toISOString() })
    currentConvId.value = data.id
    return data.id
  }

  async function remove(convId) {
    await deleteConversation(convId)
    conversations.value = conversations.value.filter(c => c.id !== convId)
    if (currentConvId.value === convId) {
      currentConvId.value = null
    }
  }

  async function loadMessages(convId) {
    return await getConversationMessages(convId)
  }

  function select(convId) {
    currentConvId.value = convId
  }

  return { conversations, currentConvId, loading, load, create, remove, loadMessages, select }
}

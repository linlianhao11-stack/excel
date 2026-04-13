import { ref } from 'vue'
import { uploadFiles as apiUpload, deleteFile as apiDelete } from '../api'

const files = ref([])
const uploading = ref(false)

export function useFiles() {
  async function upload(rawFiles) {
    uploading.value = true
    try {
      const newFiles = await apiUpload(rawFiles)
      files.value.push(...newFiles)
      return newFiles
    } finally {
      uploading.value = false
    }
  }

  async function remove(fileId) {
    await apiDelete(fileId)
    files.value = files.value.filter(f => f.file_id !== fileId)
  }

  function clear() {
    files.value = []
  }

  return { files, uploading, upload, remove, clear }
}

import { ref } from 'vue'

const collapsed = ref(false)

export function useSidebar() {
  function toggle() {
    collapsed.value = !collapsed.value
  }

  function collapse() {
    collapsed.value = true
  }

  function expand() {
    collapsed.value = false
  }

  return { collapsed, toggle, collapse, expand }
}

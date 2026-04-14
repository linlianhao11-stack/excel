<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="$emit('cancel')">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
      <div class="px-6 pt-5 pb-2">
        <h3 class="text-base font-semibold text-[#1a1a1a]">哪里不对？</h3>
        <p class="text-sm text-[#888] mt-1">选一个或自己写，我会根据你的反馈重新改</p>
      </div>

      <div class="px-6 py-3 space-y-2">
        <label
          v-for="opt in options"
          :key="opt.value"
          :class="[
            'flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-colors',
            selected === opt.value ? 'bg-blue-50 border border-blue-200' : 'border border-transparent hover:bg-[#f8f8f8]'
          ]"
        >
          <input
            type="radio"
            :value="opt.value"
            v-model="selected"
            class="mt-0.5 accent-[#3B63C9]"
          />
          <div>
            <p class="text-sm font-medium text-[#1a1a1a]">{{ opt.label }}</p>
            <p class="text-xs text-[#888]">{{ opt.desc }}</p>
          </div>
        </label>
      </div>

      <!-- 自定义输入（选 other 时展示） -->
      <div v-if="selected === 'other'" class="px-6 pb-2">
        <textarea
          v-model="customText"
          placeholder="具体说说哪里不对..."
          rows="2"
          class="w-full px-3 py-2 text-sm border border-[#d5d5d5] rounded-lg focus:outline-none focus:border-[#3B63C9] resize-none"
        />
      </div>

      <div class="flex justify-end gap-2 px-6 py-4 border-t border-[#f0f0f0]">
        <button
          @click="$emit('cancel')"
          class="px-4 py-2 text-sm text-[#555] hover:bg-[#f5f5f5] rounded-lg transition-colors cursor-pointer"
        >
          取消
        </button>
        <button
          @click="handleConfirm"
          :disabled="!selected"
          class="px-4 py-2 text-sm text-white bg-[#3B63C9] rounded-lg hover:bg-[#2B51B1] transition-colors cursor-pointer disabled:opacity-50"
        >
          确认，重新改
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['confirm', 'cancel'])

const selected = ref(null)
const customText = ref('')

const options = [
  { value: 'too_many', label: '改多了', desc: '有些不该改的被改了' },
  { value: 'too_few', label: '改少了', desc: '还有些该改的没改到' },
  { value: 'wrong', label: '改错了', desc: '改的方向/数值不对' },
  { value: 'other', label: '其他', desc: '我自己说' },
]

function handleConfirm() {
  if (!selected.value) return
  emit('confirm', {
    reasonType: selected.value,
    reasonText: selected.value === 'other' ? customText.value : '',
  })
}
</script>

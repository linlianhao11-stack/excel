<template>
  <!-- 全屏裁剪遮罩 -->
  <div
    v-if="capturing"
    class="fixed inset-0 z-[9999] cursor-crosshair select-none"
    @mousedown="startCrop"
    @mousemove="moveCrop"
    @mouseup="endCrop"
  >
    <!-- 截图背景 -->
    <canvas ref="bgCanvas" class="absolute inset-0 w-full h-full" />

    <!-- 暗色遮罩（选区外） -->
    <svg class="absolute inset-0 w-full h-full pointer-events-none">
      <defs>
        <mask id="crop-mask">
          <rect width="100%" height="100%" fill="white" />
          <rect
            v-if="hasCrop"
            :x="cropRect.x" :y="cropRect.y"
            :width="cropRect.w" :height="cropRect.h"
            fill="black"
          />
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="rgba(0,0,0,0.45)" mask="url(#crop-mask)" />
    </svg>

    <!-- 选区边框 -->
    <div
      v-if="hasCrop"
      class="absolute border-2 border-white/90 pointer-events-none"
      :style="{
        left: cropRect.x + 'px',
        top: cropRect.y + 'px',
        width: cropRect.w + 'px',
        height: cropRect.h + 'px',
        boxShadow: '0 0 0 1px rgba(0,0,0,0.3)',
      }"
    >
      <!-- 尺寸提示 -->
      <span class="absolute -top-6 left-0 text-xs text-white bg-black/60 px-1.5 py-0.5 rounded">
        {{ Math.round(cropRect.w) }} x {{ Math.round(cropRect.h) }}
      </span>
    </div>

    <!-- 底部操作栏 -->
    <div
      v-if="hasCrop && !dragging"
      class="absolute flex gap-2"
      :style="{
        left: (cropRect.x + cropRect.w - 120) + 'px',
        top: (cropRect.y + cropRect.h + 8) + 'px',
      }"
    >
      <button
        @mousedown.stop
        @click.stop="cancelCrop"
        class="px-3 py-1.5 bg-white/90 text-[#555] text-xs font-medium rounded-lg shadow hover:bg-white transition-colors"
      >
        取消
      </button>
      <button
        @mousedown.stop
        @click.stop="confirmCrop"
        class="px-3 py-1.5 bg-[#1a1a1a] text-white text-xs font-medium rounded-lg shadow hover:bg-[#333] transition-colors"
      >
        确定
      </button>
    </div>

    <!-- 提示文字 -->
    <div v-if="!hasCrop" class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-white/80 text-sm pointer-events-none">
      拖拽选择截图区域 &middot; ESC 取消
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const emit = defineEmits(['captured', 'cancel'])

const capturing = ref(false)
const bgCanvas = ref(null)
const dragging = ref(false)

// 原始截图数据
let fullImage = null  // HTMLImageElement
let screenW = 0
let screenH = 0

// 裁剪区域
const cropStart = ref({ x: 0, y: 0 })
const cropEnd = ref({ x: 0, y: 0 })
const hasCrop = ref(false)

const cropRect = computed(() => {
  const x = Math.min(cropStart.value.x, cropEnd.value.x)
  const y = Math.min(cropStart.value.y, cropEnd.value.y)
  const w = Math.abs(cropEnd.value.x - cropStart.value.x)
  const h = Math.abs(cropEnd.value.y - cropStart.value.y)
  return { x, y, w, h }
})

async function startCapture() {
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: { cursor: 'never' },
      audio: false,
    })

    // 抓一帧
    const track = stream.getVideoTracks()[0]
    const video = document.createElement('video')
    video.srcObject = stream
    video.autoplay = true

    await new Promise(resolve => {
      video.onloadeddata = resolve
    })

    // 等一帧渲染
    await new Promise(r => requestAnimationFrame(r))

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0)

    // 立即停止屏幕共享
    stream.getTracks().forEach(t => t.stop())

    // 转为图片
    const blob = await new Promise(r => canvas.toBlob(r, 'image/png'))
    fullImage = new Image()
    fullImage.src = URL.createObjectURL(blob)
    await new Promise(r => { fullImage.onload = r })

    screenW = window.innerWidth
    screenH = window.innerHeight

    // 进入裁剪模式
    capturing.value = true
    hasCrop.value = false

    // 绘制背景
    await new Promise(r => requestAnimationFrame(r))
    drawBackground()
  } catch {
    emit('cancel')
  }
}

function drawBackground() {
  const canvas = bgCanvas.value
  if (!canvas || !fullImage) return
  canvas.width = screenW
  canvas.height = screenH
  const ctx = canvas.getContext('2d')
  ctx.drawImage(fullImage, 0, 0, screenW, screenH)
}

function startCrop(e) {
  dragging.value = true
  hasCrop.value = true
  cropStart.value = { x: e.clientX, y: e.clientY }
  cropEnd.value = { x: e.clientX, y: e.clientY }
}

function moveCrop(e) {
  if (!dragging.value) return
  cropEnd.value = { x: e.clientX, y: e.clientY }
}

function endCrop() {
  dragging.value = false
  // 太小的选区视为无效
  if (cropRect.value.w < 10 || cropRect.value.h < 10) {
    hasCrop.value = false
  }
}

function cancelCrop() {
  capturing.value = false
  hasCrop.value = false
  if (fullImage) {
    URL.revokeObjectURL(fullImage.src)
    fullImage = null
  }
  emit('cancel')
}

function confirmCrop() {
  if (!fullImage) return

  const rect = cropRect.value
  // 计算原图上的实际坐标（屏幕坐标 → 原图像素）
  const scaleX = fullImage.naturalWidth / screenW
  const scaleY = fullImage.naturalHeight / screenH

  const canvas = document.createElement('canvas')
  canvas.width = Math.round(rect.w * scaleX)
  canvas.height = Math.round(rect.h * scaleY)
  const ctx = canvas.getContext('2d')
  ctx.drawImage(
    fullImage,
    Math.round(rect.x * scaleX),
    Math.round(rect.y * scaleY),
    canvas.width,
    canvas.height,
    0, 0,
    canvas.width,
    canvas.height,
  )

  canvas.toBlob((blob) => {
    const file = new File([blob], `screenshot_${Date.now()}.png`, { type: 'image/png' })
    capturing.value = false
    hasCrop.value = false
    URL.revokeObjectURL(fullImage.src)
    fullImage = null
    emit('captured', file)
  }, 'image/png')
}

// ESC 取消
function handleKeydown(e) {
  if (e.key === 'Escape' && capturing.value) {
    cancelCrop()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})

defineExpose({ startCapture })
</script>

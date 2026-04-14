<template>
  <div class="grid grid-cols-2 gap-3 w-full max-w-[540px]">
    <button
      v-for="card in cards"
      :key="card.title"
      class="flex items-start gap-3 px-4 py-3.5 rounded-xl text-left transition-colors border"
      style="background: var(--surface); border-color: var(--border)"
      @mouseenter="$event.currentTarget.style.background = 'var(--elevated)'"
      @mouseleave="$event.currentTarget.style.background = 'var(--surface)'"
      @click="$emit('select', card.prompt)"
    >
      <div
        class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
        :style="{ background: card.iconBg }"
      >
        <component :is="card.icon" class="w-4 h-4" :style="{ color: card.iconColor }" />
      </div>
      <div class="min-w-0">
        <div class="text-[14px] font-medium" style="color: var(--text)">{{ card.title }}</div>
        <div class="text-[12px] mt-0.5" style="color: var(--text-muted)">{{ card.desc }}</div>
      </div>
    </button>
  </div>
</template>

<script setup>
import { Sparkles, PenLine, BarChart3, TrendingUp } from 'lucide-vue-next'

defineEmits(['select'])

const cards = [
  {
    title: '统计分析',
    desc: '计算汇总、均值、分布等统计指标',
    prompt: '帮我对这个Excel文件进行统计分析',
    icon: BarChart3,
    iconBg: 'var(--primary-muted)',
    iconColor: 'var(--primary)',
  },
  {
    title: '数据清洗',
    desc: '去重、填充空值、格式标准化',
    prompt: '帮我清洗这个Excel文件的数据',
    icon: Sparkles,
    iconBg: 'var(--success-subtle)',
    iconColor: 'var(--success-emphasis)',
  },
  {
    title: '批量修改',
    desc: '批量替换、拆分、合并单元格内容',
    prompt: '帮我批量修改这个Excel文件',
    icon: PenLine,
    iconBg: 'var(--warning-subtle)',
    iconColor: 'var(--warning-emphasis)',
  },
  {
    title: '生成图表',
    desc: '柱状图、折线图、数据可视化',
    prompt: '帮我根据这个Excel文件生成图表',
    icon: TrendingUp,
    iconBg: 'var(--primary-muted)',
    iconColor: 'var(--primary)',
  },
]
</script>

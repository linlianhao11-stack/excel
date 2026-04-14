# CLAUDE.md — Excel Agent 项目指南

## 技术栈

### 后端
- **框架**: FastAPI + Python
- **容器**: Docker + nginx 反向代理

### 前端
- **框架**: Vue 3 (Composition API, `<script setup>`) + Vite 6
- **样式**: Tailwind CSS 4 + CSS 变量设计系统
- **状态管理**: Composables（`src/composables/`）
- **图标**: lucide-vue-next
- **Markdown**: marked + DOMPurify + highlight.js
- **HTTP**: axios

## 开发规范

- **全程使用中文沟通**，包括代码注释、commit message、文档
- **所有代码开发必须使用 superpowers skill 流程**：brainstorming → writing-plans → implementation → verification-before-completion → requesting-code-review
- 前端代码在 `frontend/src/`，构建输出到 `backend/static/`
- API 通过 `frontend/src/api/index.js` 统一管理
- Composables 在 `frontend/src/composables/`，全局单例模式

## 组件化规范

### 核心原则
- **所有 UI 必须组件化**，禁止在页面中手搓大段 HTML
- **每个组件模板不超过 150 行**，超出必须拆分子组件
- **单一职责**：每个组件只做一件事

### 组件目录结构
```
src/components/
├── layout/          # 布局组件（Sidebar, TopControls）
├── chat/            # 聊天相关（ChatPanel, ChatInput, MessageBubble, MessageList）
├── home/            # 首页相关（WelcomeHero, SuggestionCards）
├── common/          # 通用组件（AttachmentBar, ExcelPreview, SettingsModal）
└── LoginPage.vue    # 登录页
```

### 组件编写规则
- Composables 管理状态和逻辑，组件只负责展示和事件转发
- Props 向下传递数据，Events 向上通知父组件
- 禁止在子组件中直接修改父组件状态

## 设计系统

### 品牌色
- **主色 (Primary)**: Steel Blue `#3B63C9`（同 ERP-4 体系，专业可信赖）
- **主色悬停**: `#2B51B1`
- **主色激活**: `#223F8A`
- **主色柔和**: `#F0F4FF`

### 语义色（subtle 底色 + emphasis 文字，克制使用）
- **成功**: subtle `#E6F9EE` / emphasis `#166534`
- **警告**: subtle `#FFF8E6` / emphasis `#854D0E`
- **错误**: subtle `#FEF2F2` / emphasis `#991B1B`
- **信息**: subtle `#F0F4FF` / emphasis `#3B63C9`

### 中性色
- **背景**: `#F9FAFB`
- **表面**: `#FFFFFF`
- **文字主色**: `#111827`
- **文字次级**: `#4B5563`
- **文字弱化**: `#6B7280`
- **边框**: `#E5E7EB`
- **边框加重**: `#D1D5DB`

### 侧边栏
- **背景**: `#F9FAFB`
- **文字**: `#6B7280`
- **选中文字**: `#111827`
- **选中背景**: `#E5E7EB`
- **边框**: `#E5E7EB`

### 输入框
- **边框**: `#D1D5DB`
- **聚焦边框**: `#3B63C9`
- **聚焦光环**: `rgba(59, 99, 201, 0.25)`

### 设计原则
1. **对标 Claude/ChatGPT** — 交互模式、布局结构、输入框体验完全对齐主流 LLM 工具
2. **对比优先** — 黑白为底，品牌蓝点缀，层级靠粗细和大小区分
3. **功能即装饰** — 不加无意义装饰，每个视觉元素服务于功能
4. **一致到底** — 同一语义只用一个颜色值，通过 CSS 变量统一

### 反模式清单（禁止）
- 硬编码 hex 色值（必须通过 CSS 变量引用）
- 手搓 UI 组件超过 150 行模板
- 纯黑 `#000` 或纯白 `#fff`（必须微调色温）
- 弹跳/弹性动画（用 ease-out）
- `<div @click>` 代替 `<button>`
- 无 `for` 的 `<label>`

## 变更验证策略
- **首选 `npm run build`** — 编译通过即可覆盖 90% 问题
- **视觉变更用截图验证** — 关键截图对比即可
- **禁止**：逐页面循环截图验证

# Excel Agent 前端 UI 重构设计文档

> 日期：2026-04-14
> 设计稿：`/Users/lin/Desktop/Excel/ui.pen`（3 个画面 + 设计系统）

## 目标

对标 Claude / ChatGPT 的交互模式，重构前端界面：
1. 登录后进入首页模式（居中输入框 + 建议卡片），而非直接进入空对话
2. 发送第一条消息后过渡到对话模式（消息列表 + 吸底输入框）
3. 侧边栏可收起/展开
4. 输入框三层结构（附件预览 + 文本输入 + 工具栏）
5. 设置从弹窗改为独立页面
6. 全面组件化，每个组件模板不超过 150 行

## 设计稿画面

| 画面 | 描述 |
|------|------|
| Home - 首页模式 | 侧边栏 + 居中欢迎语 + 建议卡片 + 输入框 |
| Chat - 对话模式 | 侧边栏 + 消息列表 + 吸底输入框（带附件预览） |
| Settings - 设置页 | 侧边栏 + AI模型/用户管理/修改密码三区块 |
| Design System | 色板 + 字体 + 可复用组件库 |

## 品牌色体系

- **Primary**: #3B63C9 / Hover #2B51B1 / Active #223F8A / Muted #F0F4FF
- **语义色**（subtle + emphasis 克制模式）:
  - Success: #E6F9EE / #166534
  - Warning: #FFF8E6 / #854D0E
  - Error: #FEF2F2 / #991B1B
  - Info: #F0F4FF / #3B63C9
- **中性色**: #111827 → #4B5563 → #6B7280 → #9CA3AF → #D1D5DB → #E5E7EB → #F3F4F6 → #F9FAFB

## 组件架构

### 删除的组件
- `ScreenCapture.vue` — 截图改为纯粘贴，不再需要
- `SettingsModal.vue` — 改为独立页面 SettingsPage

### 新增组件
| 组件 | 目录 | 职责 |
|------|------|------|
| `SidebarHeader.vue` | layout/ | Logo + 搜索框 |
| `ConversationList.vue` | layout/ | 对话列表 + 分组逻辑 |
| `SidebarFooter.vue` | layout/ | 用户信息 + 设置/退出 |
| `TopControls.vue` | layout/ | 浮动的侧边栏收起按钮 + 新对话按钮 |
| `WelcomeHero.vue` | home/ | 欢迎标题 |
| `SuggestionCards.vue` | home/ | 建议卡片网格 |
| `MessageList.vue` | chat/ | 消息滚动区域 |
| `AttachmentBar.vue` | common/ | 统一附件预览（Excel标签 + 图片缩略图） |
| `SettingsPage.vue` | — | 设置独立页面（AI模型/用户/密码） |

### 改造的组件
| 组件 | 改动 |
|------|------|
| `App.vue` | 删除顶栏 header、增加设置页路由切换 |
| `Sidebar.vue` | 拆分为 Header/List/Footer 三个子组件，支持收起/展开 |
| `ChatPanel.vue` | 双模式布局（首页/对话），根据 hasMessages 切换 |
| `ChatInput.vue` | 三层重构：附件预览层 + 文本层 + 工具栏层；删除截图按钮；Excel标签移入 |

### 新增 Composable
| 名称 | 职责 |
|------|------|
| `useSidebar.js` | 侧边栏展开/收起状态管理 |

## 交互流程

### 首页 → 对话过渡
1. 用户在首页输入框输入文字或点击建议卡片
2. `ChatPanel` 检测到 `messages.length > 0`
3. 欢迎语 + 建议卡片消失，消息列表出现
4. 输入框从居中位置移到底部固定

### 侧边栏收起/展开
1. 点击左上角 `panel-left` 图标
2. `useSidebar` 切换 `collapsed` 状态
3. 侧边栏宽度从 260px 过渡到 0（完全隐藏）
4. 主内容区占满全宽

### 设置页进入/退出
1. 点击侧边栏底部设置图标
2. 主内容区切换为 SettingsPage（不是弹窗）
3. 点击侧边栏对话或新对话按钮返回聊天

## CSS 变量体系

所有色值通过 `main.css` 中的 CSS 变量定义，组件中禁止硬编码色值：
```css
:root {
  --primary: #3B63C9;
  --primary-hover: #2B51B1;
  --primary-muted: #F0F4FF;
  --text: #111827;
  --text-secondary: #4B5563;
  --text-muted: #6B7280;
  --border: #E5E7EB;
  --border-strong: #D1D5DB;
  --surface: #FFFFFF;
  --background: #F9FAFB;
  --elevated: #F3F4F6;
  /* ... 完整定义见 CLAUDE.md */
}
```

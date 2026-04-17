# 认证系统增强设计

**日期**：2026-04-17
**状态**：设计已确认，待编写实施计划

## 背景

当前 Excel Agent 项目的认证体系只支持：登录、管理员创建用户、管理员删除用户、用户改自己的密码。JWT 7 天长期有效，无 idle 超时机制，无用户自注册入口。

本次增强目标：
1. **开放自注册**：访客可通过登录页进入注册页创建账号
2. **管理员开关注册**：可在设置中关闭自注册通道
3. **账号启用/禁用**：管理员可临时禁用账号，被禁用账号立即失效
4. **管理员重置他人密码**：带二次确认
5. **30 分钟无操作自动回登录页**：保障用户离座安全

## 方案

采用"最小改动 + 滑动 token"方案。在现有 `auth.py` 基础上扩展端点与依赖，前端在登录页上并列"登录 / 注册"，设置页扩展用户管理能力。

### 核心机制

- **JWT 短期 + 响应头滑动刷新**：JWT 有效期从 7 天缩短为 30 分钟；每次受鉴权请求，后端在响应头写入 `X-New-Token`（仅当剩余有效期 <15 分钟时刷新，节流避免重复签发）；前端在 axios 响应拦截器 / fetch 响应到达时读取并更新 `localStorage`
- **活跃状态即时校验**：`get_current_user` 依赖在解码 JWT 后**额外查 DB 校验 `is_active`**，禁用用户立即 401
- **注册开关**：存于 `settings` 表 `allow_registration` 键，默认 `true`；提供**公开的**只读端点供登录页查询；写端点需管理员

## 数据模型变更

### `users` 表新增字段

```sql
ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1;
```

- 旧行自动填 1（保持兼容）
- 登录时校验 `is_active=1`，否则返回"账号已被禁用"
- 每次鉴权请求校验 `is_active`，禁用态 token 立即 401

### `settings` 表新增键

- `allow_registration`：`"true"` / `"false"`，默认 `"true"`
- `init_db()` 初始化时若无此键则写入 `"true"`

## 后端接口

### 新增

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/auth/register` | 公开 | 自注册，开关关闭时返回 403 |
| GET | `/api/auth/config` | 公开 | 返回 `{allow_registration: bool}`，登录页读取 |
| PUT | `/api/auth/config` | 管理员 | 更新 `allow_registration` |
| POST | `/api/auth/users/{user_id}/reset-password` | 管理员 | 重置任意用户密码 |
| PATCH | `/api/auth/users/{user_id}/active` | 管理员 | 启用/禁用账号（禁自己返回 400） |

### 修改

- `POST /api/auth/login`：校验 `is_active=1`，禁用返回 401 "账号已被禁用"
- `get_current_user` 依赖：解码 JWT 后额外查 DB 的 `is_active`；新增响应头 `X-New-Token` 逻辑（通过 `Response` 参数注入或中间件统一处理）
- `GET /api/auth/users`：返回字段增加 `is_active`

### 请求/响应契约

```python
class RegisterRequest(BaseModel):
    username: str
    password: str

class ResetPasswordRequest(BaseModel):
    new_password: str

class SetActiveRequest(BaseModel):
    is_active: bool

class AuthConfigRequest(BaseModel):
    allow_registration: bool
```

注册成功直接返回 `token + user`（等同登录），注册后立即登录态。

### Token 刷新实现细节

采用 **FastAPI middleware** 或 **自定义依赖 + Response 注入** 二选一。选 middleware：

```python
@app.middleware("http")
async def refresh_token_middleware(request: Request, call_next):
    response = await call_next(request)
    # 仅对鉴权请求处理
    payload = getattr(request.state, "user_payload", None)
    if payload:
        remaining = payload["exp"] - datetime.utcnow().timestamp()
        if remaining < 15 * 60:  # 剩余 <15 分钟
            new_token = create_token(payload["user_id"], payload["username"], payload["is_admin"])
            response.headers["X-New-Token"] = new_token
    return response
```

`get_current_user` 把 payload 挂到 `request.state.user_payload`，middleware 据此判断是否刷新。

## 前端改造

### 路由 / 视图

`App.vue` 的 `isLoggedIn` 分支维持；`LoginPage.vue` 内部新增 `mode` 状态（`'login'` / `'register'`），默认 `login`，**登录按钮旁边**加"注册"按钮切换到 register 模式。

### 新增 / 修改文件

| 文件 | 动作 | 说明 |
|---|---|---|
| `components/LoginPage.vue` | 修改 | 加 mode 切换，按钮并列"登录 / 注册"；注册 mode 时有"返回登录"入口；进入页面时调 `/api/auth/config` 决定是否显示注册入口 |
| `composables/useAuth.js` | 修改 | 加 `register(username, password)`；在 token 变更时双向同步 localStorage |
| `api/index.js` | 修改 | axios response 拦截器读 `X-New-Token` 更新；fetch SSE 调用处（chat、diff/reject）读 `response.headers.get('X-New-Token')` 更新；新增 `register` / `getAuthConfig` / `setAuthConfig` / `resetUserPassword` / `setUserActive` |
| `composables/useIdleTimer.js` | **可选**（不新增）| 不需要，idle 超时由后端 JWT 过期触发 401，前端拦截器已自动跳登录 |
| `components/settings/UserManagement.vue` | 修改 | 每行加"改密码"按钮（触发弹窗）、"禁用 / 启用"切换、展示 `is_active` 状态；禁/删自己禁用 |
| `components/settings/AdminResetPasswordModal.vue` | **新增** | 改他人密码的弹窗：输入新密码 + 二次确认 |
| `components/SettingsPage.vue` | 修改 | 加"注册开关"section（管理员可见），读写 `/api/auth/config` |

### 前端 token 刷新核心代码

```js
// axios 响应拦截器
api.interceptors.response.use(
  (res) => {
    const newToken = res.headers['x-new-token']
    if (newToken) updateToken(newToken)
    return res
  },
  (err) => { /* 原 401 逻辑 */ }
)

// fetch SSE 入口（chat / diff）
fetch(...).then(response => {
  const newToken = response.headers.get('X-New-Token')
  if (newToken) updateToken(newToken)
  // 继续原有流处理
})

function updateToken(newToken) {
  // 只在新 token exp 更晚时替换，避免并发竞争
  const cur = localStorage.getItem('token')
  if (!cur || decodeExp(newToken) > decodeExp(cur)) {
    localStorage.setItem('token', newToken)
  }
}
```

### 空闲 30 分钟回登录的触发路径

1. 用户 30 分钟无任何操作 → 无请求发出 → 后端无刷新机会 → 当前 token 30 分钟后过期
2. 用户下次操作（发消息 / 切对话 / 打开设置）→ 请求带过期 token → 后端 401
3. axios 拦截器捕获 401 → 清 localStorage → `window.location.reload()` → 回登录页

**无需前端计时器**，滑动窗口本身即是 idle 退出。

## 错误处理

| 场景 | HTTP | 错误消息 |
|---|---|---|
| 注册开关关闭 | 403 | 注册功能已关闭 |
| 注册用户名重复 | 400 | 用户名已存在 |
| 登录时账号被禁用 | 401 | 账号已被禁用，请联系管理员 |
| 鉴权时账号被禁用 | 401 | 账号已被禁用 |
| Token 过期 | 401 | 登录已过期，请重新登录 |
| 管理员禁用/删除自己 | 400 | 不能禁用/删除自己 |
| 改他人密码时新密码为空 | 400 | 新密码不能为空 |

所有 401 走前端统一拦截器跳转登录。

## 测试策略

### 后端（手动 + curl 脚本）
- 注册开/关切换 → 注册端点 200 / 403
- 注册成功后立即返回可用 token
- 禁用用户登录 → 401
- 在线用户被禁用 → 下一请求 401
- Token 剩余 <15 分钟 → 响应头出现 `X-New-Token`
- Token 剩余 >15 分钟 → 响应头无 `X-New-Token`
- Token 过期 → 401
- 管理员重置他人密码 → 新密码可登录
- 管理员禁自己 → 400

### 前端
- 登录页注册按钮在开关开时显示、关时隐藏
- 注册流程 → 自动登录 → 进入首页
- 设置页管理员区域显示注册开关和完整用户管理
- 非管理员进入设置看不到注册开关和用户管理
- 改他人密码弹窗二次确认后提交

### 验证标准
- `npm run build` 通过
- 关键视觉：登录页（含注册入口）、注册页、设置页用户管理截图对比

## 非目标（不做）

- 密码强度校验（用户已选 C：无要求）
- 邮箱验证 / 找回密码
- access + refresh token 双 token 机制
- 前端 idle 计时器（已由后端 JWT 过期覆盖）
- 审计日志
- 管理员可编辑 `is_admin` 标记（本次不做，保持只在创建时定）

## 部署影响

- 数据库迁移：启动时 `init_db()` 里追加 `ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1`（用 `try/except` 兼容已存在的情况）
- 初始化：`allow_registration` 若无则写 `"true"`
- 按 CLAUDE.md 部署流程 scp + 重建即可

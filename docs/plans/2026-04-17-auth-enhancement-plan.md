# 认证系统增强实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Excel Agent 增加用户自注册、注册开关、账号启用/禁用、管理员重置他人密码、30 分钟无操作自动回登录页。

**Architecture:** 沿用现有 FastAPI + SQLite + Vue 3 架构。后端在 `auth.py` 扩展端点 + 中间件实现 JWT 滑动刷新；前端在登录页加注册子视图，设置页扩展用户管理能力。JWT 30 分钟短期 + 响应头 `X-New-Token` 滑动刷新，idle 超时自然过期触发 401 回登录。

**Tech Stack:** FastAPI / PyJWT / bcrypt / SQLite、Vue 3 `<script setup>` / axios / Tailwind CSS 4

**设计文档:** `docs/plans/2026-04-17-auth-enhancement-design.md`

**验证方式（本项目无测试框架）:**
- 后端用 `curl` 或 httpie 逐端点验证
- 前端用 `npm run build` + 浏览器手动验证
- 参考 CLAUDE.md 规范：组件 ≤150 行、中文沟通、品牌色 CSS 变量

---

## 任务索引

- Task 1: 数据库迁移（`is_active` + `allow_registration`）
- Task 2: JWT 配置改 30 分钟 + create_token 调整
- Task 3: `get_current_user` 加 `is_active` 校验 + state 注入
- Task 4: Token 刷新中间件（`X-New-Token` 响应头）
- Task 5: 登录端点加 `is_active` 检查
- Task 6: `GET /api/auth/config` 公开端点
- Task 7: `PUT /api/auth/config` 管理员端点
- Task 8: `POST /api/auth/register` 注册端点
- Task 9: `POST /api/auth/users/{id}/reset-password` 管理员重置
- Task 10: `PATCH /api/auth/users/{id}/active` 启用/禁用
- Task 11: `list_users` 返回 `is_active`
- Task 12: 前端 API 层：新增端点 + `X-New-Token` 拦截
- Task 13: `useAuth.js` 加 `register` + `updateToken`
- Task 14: `LoginForm.vue` 拆出
- Task 15: `RegisterForm.vue` 新建
- Task 16: `LoginPage.vue` 改为 shell（mode 切换）
- Task 17: `UserListRow.vue` 新建
- Task 18: `AdminResetPasswordModal.vue` 新建
- Task 19: `UserManagement.vue` 重构（用 UserListRow + 弹窗）
- Task 20: `RegistrationToggle.vue` 新建
- Task 21: `SettingsPage.vue` 接入注册开关
- Task 22: 前端 build 验证 + 浏览器端到端手动验证
- Task 23: 部署到 NAS

---

## Task 1: 数据库迁移

**Files:**
- Modify: `backend/app/database.py`

**Step 1: 查看现状**

Run: `grep -n "SCHEMA" ~/Desktop/Excel/backend/app/database.py | head -5`
Expected: 看到 SCHEMA 常量和 `users` 表定义

**Step 2: 修改 `SCHEMA` 常量，为 `users` 表加 `is_active`**

在 `CREATE TABLE IF NOT EXISTS users` 内增加字段（新部署直接建好）：

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Step 3: 在 `init_db()` 里加兼容迁移（已有库补字段）**

在 `conn.executescript(SCHEMA)` 之后、创建默认 admin 之前插入：

```python
# 兼容已存在的库：若 is_active 列缺失则补上
cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
if "is_active" not in cols:
    conn.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
    conn.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
    conn.commit()
```

**Step 4: 在 `init_db()` 末尾为 `settings` 写入 `allow_registration` 默认值**

在 `defaults` 字典循环之后加：

```python
# 注册开关默认开启
existing = conn.execute(
    "SELECT key FROM settings WHERE key = ?", ("allow_registration",)
).fetchone()
if not existing:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        ("allow_registration", "true"),
    )
    conn.commit()
```

**Step 5: 手动验证迁移**

```bash
cd ~/Desktop/Excel/backend
mkdir -p /tmp/excel_mig && rm -f /tmp/excel_mig/excel_agent.db
DB_DIR=/tmp/excel_mig python -c "from app.database import init_db; init_db()"
sqlite3 /tmp/excel_mig/excel_agent.db ".schema users"
sqlite3 /tmp/excel_mig/excel_agent.db "SELECT * FROM settings WHERE key='allow_registration';"
```

Expected: `users` 表含 `is_active`，`settings` 里 `allow_registration = true`

再验证兼容迁移（用旧 schema 模拟已有库）：

```bash
rm -f /tmp/excel_mig/excel_agent.db
sqlite3 /tmp/excel_mig/excel_agent.db "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, is_admin BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP); CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);"
DB_DIR=/tmp/excel_mig python -c "from app.database import init_db; init_db()"
sqlite3 /tmp/excel_mig/excel_agent.db ".schema users"
```

Expected: 老表成功加了 `is_active` 列，无报错

**Step 6: 提交**

```bash
cd ~/Desktop/Excel
git add backend/app/database.py
git commit -m "feat(auth): users 加 is_active 字段 + allow_registration 默认设置"
```

---

## Task 2: JWT 过期时间 30 分钟 + create_token 签名保持不变

**Files:**
- Modify: `backend/app/api/auth.py:16`

**Step 1: 改常量**

把 `backend/app/api/auth.py` 中的：

```python
JWT_EXPIRE_DAYS = 7
```

改为：

```python
JWT_EXPIRE_MINUTES = 30
```

**Step 2: 改 `create_token` 函数**

把：

```python
"exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
```

改为：

```python
"exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
```

**Step 3: 导入 `create_token` 的所有位置都不变（签名不变）**

Run: `grep -rn "JWT_EXPIRE" ~/Desktop/Excel/backend/`
Expected: 只有 auth.py 用到，其他文件无需改

**Step 4: 手动验证 token 过期时间**

```bash
cd ~/Desktop/Excel/backend
python -c "
import sys; sys.path.insert(0, '.')
from app.api.auth import create_token
import jwt, os
t = create_token(1, 'test', False)
p = jwt.decode(t, os.environ.get('JWT_SECRET', 'excel-agent-secret-change-me'), algorithms=['HS256'])
from datetime import datetime
print('exp:', datetime.utcfromtimestamp(p['exp']))
print('now:', datetime.utcnow())
print('delta_min:', (p['exp'] - datetime.utcnow().timestamp()) / 60)
"
```

Expected: `delta_min` 约 30

**Step 5: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): JWT 过期从 7 天改为 30 分钟"
```

---

## Task 3: `get_current_user` 加 `is_active` 校验 + 注入 request.state

**Files:**
- Modify: `backend/app/api/auth.py:45-57`

**Step 1: 改写 `get_current_user`**

用下面完整实现替换当前 `get_current_user` 函数：

```python
def get_current_user(request: Request) -> dict:
    """FastAPI 依赖：解析 token + 校验账号仍有效"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的登录凭证")

    # 实时校验账号是否被禁用
    conn = get_db()
    row = conn.execute(
        "SELECT is_active FROM users WHERE id = ?", (payload["user_id"],)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "账号不存在")
    if not row["is_active"]:
        raise HTTPException(401, "账号已被禁用")

    # 注入 state，供 refresh 中间件读取
    request.state.user_payload = payload
    return payload
```

**Step 2: 手动验证**

启动本地 dev server：

```bash
cd ~/Desktop/Excel/backend
DB_DIR=/tmp/exceldev uvicorn main:app --port 8910 --reload &
sleep 2
# 登录拿 token
TOKEN=$(curl -s -X POST http://localhost:8910/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['token'])")
# 测试 /me
curl -s http://localhost:8910/api/auth/me -H "Authorization: Bearer $TOKEN"
# 禁用 admin（模拟）
sqlite3 /tmp/exceldev/excel_agent.db "UPDATE users SET is_active = 0 WHERE username='admin'"
# 再试
curl -s http://localhost:8910/api/auth/me -H "Authorization: Bearer $TOKEN"
```

Expected: 第一次返回 user，第二次返回 `{"detail":"账号已被禁用"}`

还原：`sqlite3 /tmp/exceldev/excel_agent.db "UPDATE users SET is_active = 1 WHERE username='admin'"`

**Step 3: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): get_current_user 实时校验 is_active + 注入 state"
```

---

## Task 4: Token 刷新中间件

**Files:**
- Modify: `backend/main.py`

**Step 1: 查看 main.py 当前结构**

```bash
cat ~/Desktop/Excel/backend/main.py
```

**Step 2: 在 main.py 中注册中间件**

在 app 创建之后、`include_router` 之前加：

```python
from datetime import datetime
from app.api.auth import create_token

REFRESH_THRESHOLD_SECONDS = 15 * 60  # 剩余 <15 分钟才刷新

@app.middleware("http")
async def refresh_token_middleware(request, call_next):
    response = await call_next(request)
    payload = getattr(request.state, "user_payload", None)
    if payload:
        remaining = payload["exp"] - datetime.utcnow().timestamp()
        if 0 < remaining < REFRESH_THRESHOLD_SECONDS:
            new_token = create_token(
                payload["user_id"], payload["username"], payload["is_admin"]
            )
            response.headers["X-New-Token"] = new_token
    return response
```

**Step 3: 手动验证**

重启 dev server 后构造一个即将过期的 token 测试：

```bash
cd ~/Desktop/Excel/backend
# 先构造一个剩余 5 分钟的 token
NEAR_EXP_TOKEN=$(python -c "
import jwt, os
from datetime import datetime, timedelta
payload = {'user_id': 1, 'username': 'admin', 'is_admin': True, 'exp': datetime.utcnow() + timedelta(minutes=5)}
print(jwt.encode(payload, os.environ.get('JWT_SECRET', 'excel-agent-secret-change-me'), algorithm='HS256'))
")
# 发请求看响应头
curl -s -i http://localhost:8910/api/auth/me -H "Authorization: Bearer $NEAR_EXP_TOKEN" | grep -i x-new-token
```

Expected: 出现 `X-New-Token: eyJ...` 响应头

再测试：正常 30 分钟 token 不应触发刷新
```bash
FRESH_TOKEN=$(curl -s -X POST http://localhost:8910/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -i http://localhost:8910/api/auth/me -H "Authorization: Bearer $FRESH_TOKEN" | grep -i x-new-token
```

Expected: 无 `X-New-Token` 响应头（剩余 ~30 分钟 > 15 分钟阈值）

**Step 4: 提交**

```bash
git add backend/main.py
git commit -m "feat(auth): 加 JWT 滑动刷新中间件（X-New-Token 响应头）"
```

---

## Task 5: 登录端点加 `is_active` 检查

**Files:**
- Modify: `backend/app/api/auth.py:66-89`

**Step 1: 改写 login 函数**

找到 `@router.post("/login")` 装饰的 `login` 函数，把 SQL 改为同时查 `is_active`，并在密码校验后加禁用判断：

```python
@router.post("/login")
async def login(req: LoginRequest):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password_hash, is_admin, is_active FROM users WHERE username = ?",
        (req.username,),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(401, "用户名或密码错误")

    if not bcrypt.checkpw(req.password.encode(), row["password_hash"].encode()):
        raise HTTPException(401, "用户名或密码错误")

    if not row["is_active"]:
        raise HTTPException(401, "账号已被禁用，请联系管理员")

    token = create_token(row["id"], row["username"], bool(row["is_admin"]))
    return {
        "token": token,
        "user": {
            "id": row["id"],
            "username": row["username"],
            "is_admin": bool(row["is_admin"]),
        },
    }
```

**Step 2: 手动验证**

```bash
# 禁用 admin
sqlite3 /tmp/exceldev/excel_agent.db "UPDATE users SET is_active = 0 WHERE username='admin'"
curl -s -X POST http://localhost:8910/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'
# 恢复
sqlite3 /tmp/exceldev/excel_agent.db "UPDATE users SET is_active = 1 WHERE username='admin'"
curl -s -X POST http://localhost:8910/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'
```

Expected: 第一次 `{"detail":"账号已被禁用，请联系管理员"}`，第二次正常返回 token

**Step 3: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): 登录时校验 is_active，禁用账号拒绝登录"
```

---

## Task 6: `GET /api/auth/config` 公开端点

**Files:**
- Modify: `backend/app/api/auth.py`

**Step 1: 导入 `get_setting`**

在 auth.py 顶部导入行补一个：

```python
from ..database import get_db, get_setting, set_setting
```

（若 get_setting 已导入可跳过）

**Step 2: 在文件末尾加端点**

```python
@router.get("/config")
async def get_auth_config():
    """公开的认证配置，用于登录页决定是否显示注册入口"""
    allow = get_setting("allow_registration", "true") == "true"
    return {"allow_registration": allow}
```

**Step 3: 手动验证**

```bash
curl -s http://localhost:8910/api/auth/config
# 关掉
sqlite3 /tmp/exceldev/excel_agent.db "UPDATE settings SET value='false' WHERE key='allow_registration'"
curl -s http://localhost:8910/api/auth/config
# 恢复
sqlite3 /tmp/exceldev/excel_agent.db "UPDATE settings SET value='true' WHERE key='allow_registration'"
```

Expected: 第一次 `{"allow_registration":true}`，第二次 `{"allow_registration":false}`

**Step 4: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): GET /api/auth/config 公开注册开关状态"
```

---

## Task 7: `PUT /api/auth/config` 管理员端点

**Files:**
- Modify: `backend/app/api/auth.py`

**Step 1: 加请求模型**

在其他 `class ...Request(BaseModel)` 附近加：

```python
class AuthConfigRequest(BaseModel):
    allow_registration: bool
```

**Step 2: 加端点**

```python
@router.put("/config")
async def update_auth_config(
    req: AuthConfigRequest, admin: dict = Depends(require_admin)
):
    set_setting("allow_registration", "true" if req.allow_registration else "false")
    return {"ok": True}
```

**Step 3: 手动验证**

```bash
TOKEN=$(curl -s -X POST http://localhost:8910/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
# 关闭注册
curl -s -X PUT http://localhost:8910/api/auth/config -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"allow_registration":false}'
curl -s http://localhost:8910/api/auth/config
# 恢复
curl -s -X PUT http://localhost:8910/api/auth/config -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"allow_registration":true}'
```

Expected: PUT 返回 `{"ok":true}`，GET 能反映最新值

**Step 4: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): PUT /api/auth/config 管理员切换注册开关"
```

---

## Task 8: `POST /api/auth/register` 注册端点

**Files:**
- Modify: `backend/app/api/auth.py`

**Step 1: 加请求模型**

```python
class RegisterRequest(BaseModel):
    username: str
    password: str
```

**Step 2: 加端点**

```python
@router.post("/register")
async def register(req: RegisterRequest):
    allow = get_setting("allow_registration", "true") == "true"
    if not allow:
        raise HTTPException(403, "注册功能已关闭")

    if not req.username or not req.password:
        raise HTTPException(400, "用户名和密码不能为空")

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (req.username,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "用户名已存在")

    pw_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, is_admin, is_active) VALUES (?, ?, 0, 1)",
        (req.username, pw_hash),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()

    token = create_token(user_id, req.username, False)
    return {
        "token": token,
        "user": {"id": user_id, "username": req.username, "is_admin": False},
    }
```

**Step 3: 手动验证**

```bash
# 正常注册
curl -s -X POST http://localhost:8910/api/auth/register -H "Content-Type: application/json" -d '{"username":"testu1","password":"pass1"}'
# 重复
curl -s -X POST http://localhost:8910/api/auth/register -H "Content-Type: application/json" -d '{"username":"testu1","password":"pass1"}'
# 关闭后
sqlite3 /tmp/exceldev/excel_agent.db "UPDATE settings SET value='false' WHERE key='allow_registration'"
curl -s -X POST http://localhost:8910/api/auth/register -H "Content-Type: application/json" -d '{"username":"testu2","password":"pass2"}'
sqlite3 /tmp/exceldev/excel_agent.db "UPDATE settings SET value='true' WHERE key='allow_registration'"
# 清理测试用户
sqlite3 /tmp/exceldev/excel_agent.db "DELETE FROM users WHERE username='testu1'"
```

Expected:
1. 首次成功返回 token + user
2. 重复返回 `{"detail":"用户名已存在"}`
3. 关闭状态返回 `{"detail":"注册功能已关闭"}`

**Step 4: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): POST /api/auth/register 自注册端点"
```

---

## Task 9: `POST /api/auth/users/{id}/reset-password` 管理员重置

**Files:**
- Modify: `backend/app/api/auth.py`

**Step 1: 加请求模型**

```python
class ResetPasswordRequest(BaseModel):
    new_password: str
```

**Step 2: 加端点**

```python
@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: int,
    req: ResetPasswordRequest,
    admin: dict = Depends(require_admin),
):
    if not req.new_password:
        raise HTTPException(400, "新密码不能为空")

    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "用户不存在")

    pw_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}
```

**Step 3: 手动验证**

```bash
# 先创建一个测试用户
curl -s -X POST http://localhost:8910/api/auth/register -H "Content-Type: application/json" -d '{"username":"rpu","password":"old"}'
# 管理员重置
TUID=$(sqlite3 /tmp/exceldev/excel_agent.db "SELECT id FROM users WHERE username='rpu'")
curl -s -X POST http://localhost:8910/api/auth/users/$TUID/reset-password -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"new_password":"newpw"}'
# 用新密码登录
curl -s -X POST http://localhost:8910/api/auth/login -H "Content-Type: application/json" -d '{"username":"rpu","password":"newpw"}'
# 清理
sqlite3 /tmp/exceldev/excel_agent.db "DELETE FROM users WHERE username='rpu'"
```

Expected: 重置后新密码能登录

**Step 4: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): POST /users/{id}/reset-password 管理员重置密码"
```

---

## Task 10: `PATCH /api/auth/users/{id}/active` 启用/禁用

**Files:**
- Modify: `backend/app/api/auth.py`

**Step 1: 加请求模型**

```python
class SetActiveRequest(BaseModel):
    is_active: bool
```

**Step 2: 加端点**

```python
@router.patch("/users/{user_id}/active")
async def set_user_active(
    user_id: int,
    req: SetActiveRequest,
    admin: dict = Depends(require_admin),
):
    if user_id == admin["user_id"] and not req.is_active:
        raise HTTPException(400, "不能禁用自己")

    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "用户不存在")

    conn.execute(
        "UPDATE users SET is_active = ? WHERE id = ?",
        (1 if req.is_active else 0, user_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}
```

**Step 3: 手动验证**

```bash
# 创建测试用户
curl -s -X POST http://localhost:8910/api/auth/register -H "Content-Type: application/json" -d '{"username":"setu","password":"p"}'
TUID=$(sqlite3 /tmp/exceldev/excel_agent.db "SELECT id FROM users WHERE username='setu'")
# 禁用
curl -s -X PATCH http://localhost:8910/api/auth/users/$TUID/active -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"is_active":false}'
sqlite3 /tmp/exceldev/excel_agent.db "SELECT username, is_active FROM users WHERE id=$TUID"
# 管理员禁自己
ADMIN_ID=$(sqlite3 /tmp/exceldev/excel_agent.db "SELECT id FROM users WHERE username='admin'")
curl -s -X PATCH http://localhost:8910/api/auth/users/$ADMIN_ID/active -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"is_active":false}'
# 清理
sqlite3 /tmp/exceldev/excel_agent.db "DELETE FROM users WHERE username='setu'"
```

Expected:
- 禁用 `setu` 后 is_active=0
- 管理员禁自己返回 `{"detail":"不能禁用自己"}`

**Step 4: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): PATCH /users/{id}/active 启用/禁用账号"
```

---

## Task 11: `list_users` 返回 `is_active`

**Files:**
- Modify: `backend/app/api/auth.py`（`list_users` 函数）

**Step 1: 改 SQL**

把：

```python
"SELECT id, username, is_admin, created_at FROM users"
```

改为：

```python
"SELECT id, username, is_admin, is_active, created_at FROM users ORDER BY id"
```

**Step 2: 手动验证**

```bash
curl -s http://localhost:8910/api/auth/users -H "Authorization: Bearer $TOKEN"
```

Expected: 每条用户数据含 `is_active: 1` 或 `0`

**Step 3: 提交**

```bash
git add backend/app/api/auth.py
git commit -m "feat(auth): list_users 返回 is_active 字段"
```

---

## Task 12: 前端 API 层扩展

**Files:**
- Modify: `frontend/src/api/index.js`

**Step 1: 加 token 更新工具函数（顶部）**

在 `const api = axios.create(...)` 之后、拦截器之前加：

```js
function decodeExp(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp || 0
  } catch { return 0 }
}

function updateTokenIfNewer(newToken) {
  if (!newToken) return
  const cur = localStorage.getItem('token')
  if (!cur || decodeExp(newToken) > decodeExp(cur)) {
    localStorage.setItem('token', newToken)
  }
}
```

**Step 2: 改 axios 响应拦截器**

把：

```js
api.interceptors.response.use(
  (res) => res,
  (err) => { ... }
)
```

改为：

```js
api.interceptors.response.use(
  (res) => {
    const newToken = res.headers['x-new-token']
    if (newToken) updateTokenIfNewer(newToken)
    return res
  },
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.reload()
    }
    return Promise.reject(err)
  }
)
```

**Step 3: 在 `chatStream` 和 `rejectDiffStream` 里读 `X-New-Token`**

两处 fetch 的 `.then(async (response) => {` 开头增加：

```js
// 读滑动刷新的新 token
const _newToken = response.headers.get('X-New-Token')
if (_newToken) updateTokenIfNewer(_newToken)
```

注意放在 `if (response.status === 401)` 之后（401 时跳过）。

**Step 4: 加新端点调用（文件末尾）**

```js
// 认证配置
export async function getAuthConfig() {
  const { data } = await api.get('/auth/config')
  return data
}

export async function setAuthConfig(allowRegistration) {
  const { data } = await api.put('/auth/config', { allow_registration: allowRegistration })
  return data
}

// 自注册
export async function registerUser(username, password) {
  const { data } = await api.post('/auth/register', { username, password })
  return data
}

// 管理员重置他人密码
export async function adminResetPassword(userId, newPassword) {
  const { data } = await api.post(`/auth/users/${userId}/reset-password`, { new_password: newPassword })
  return data
}

// 启用/禁用账号
export async function setUserActive(userId, isActive) {
  const { data } = await api.patch(`/auth/users/${userId}/active`, { is_active: isActive })
  return data
}
```

**Step 5: 提交**

```bash
git add frontend/src/api/index.js
git commit -m "feat(auth): 前端 API 层新增注册/配置/重置/禁用端点 + X-New-Token 刷新"
```

---

## Task 13: `useAuth.js` 加 `register` 方法

**Files:**
- Modify: `frontend/src/composables/useAuth.js`

**理念**：token 滑动刷新只更新 localStorage，不改变登录态。UI 层 `isLoggedIn` 判断与当前 token 的时效无关，只要 localStorage 有 token 就视为已登录。请求发起时 axios 拦截器总是读最新 `localStorage.getItem('token')`。因此不需要跨 tab 同步 / 轮询，保持最小改动。

**Step 1: 改写整个文件**

完整替换：

```js
import { ref, computed } from 'vue'
import axios from 'axios'

const token = ref(localStorage.getItem('token') || '')
const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

export function useAuth() {
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin || false)

  async function login(username, password) {
    const { data } = await axios.post('/api/auth/login', { username, password })
    token.value = data.token
    user.value = data.user
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))
    return data
  }

  async function register(username, password) {
    const { data } = await axios.post('/api/auth/register', { username, password })
    token.value = data.token
    user.value = data.user
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))
    return data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, isAdmin, login, register, logout }
}
```

**Step 2: 手动验证**

```bash
cd ~/Desktop/Excel/frontend
npm run build
```

Expected: build 通过

**Step 3: 提交**

```bash
git add frontend/src/composables/useAuth.js
git commit -m "feat(auth): useAuth 加 register 方法"
```

---

## Task 14: `LoginForm.vue` 从 LoginPage 抽出

**Files:**
- Create: `frontend/src/components/auth/LoginForm.vue`

**Step 1: 创建文件**

```vue
<template>
  <form @submit.prevent="handleSubmit" class="space-y-4">
    <div>
      <input
        v-model="username"
        type="text"
        placeholder="用户名"
        autocomplete="username"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{
          borderColor: 'var(--input-border)',
          color: 'var(--text)',
        }"
      />
    </div>
    <div>
      <input
        v-model="password"
        type="password"
        placeholder="密码"
        autocomplete="current-password"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{
          borderColor: 'var(--input-border)',
          color: 'var(--text)',
        }"
      />
    </div>

    <div
      v-if="error"
      class="px-3 py-2 text-sm rounded-lg border"
      :style="{
        background: 'var(--error-subtle)',
        color: 'var(--error-emphasis)',
        borderColor: 'var(--error-subtle)',
      }"
    >{{ error }}</div>

    <div class="flex gap-2">
      <button
        type="submit"
        :disabled="loading"
        class="flex-1 py-2.5 text-white text-[15px] font-medium rounded-xl disabled:opacity-50 transition-colors"
        :style="{ background: 'var(--primary)' }"
      >
        {{ loading ? '登录中...' : '登录' }}
      </button>
      <button
        v-if="allowRegistration"
        type="button"
        @click="$emit('switchToRegister')"
        class="px-4 py-2.5 text-[15px] font-medium rounded-xl border transition-colors"
        :style="{ borderColor: 'var(--border)', color: 'var(--text)' }"
      >
        注册
      </button>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { useAuth } from '../../composables/useAuth'

const props = defineProps({
  allowRegistration: { type: Boolean, default: false }
})
defineEmits(['switchToRegister'])

const { login } = useAuth()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  if (!username.value || !password.value) return
  error.value = ''
  loading.value = true
  try {
    await login(username.value, password.value)
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
```

**Step 2: 提交**

```bash
mkdir -p ~/Desktop/Excel/frontend/src/components/auth
git add frontend/src/components/auth/LoginForm.vue
git commit -m "feat(auth): 抽出 LoginForm.vue 子组件（带注册入口按钮）"
```

---

## Task 15: `RegisterForm.vue` 新建

**Files:**
- Create: `frontend/src/components/auth/RegisterForm.vue`

**Step 1: 创建文件**

```vue
<template>
  <form @submit.prevent="handleSubmit" class="space-y-4">
    <div>
      <input
        v-model="username"
        type="text"
        placeholder="用户名"
        autocomplete="username"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)' }"
      />
    </div>
    <div>
      <input
        v-model="password"
        type="password"
        placeholder="密码"
        autocomplete="new-password"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)' }"
      />
    </div>
    <div>
      <input
        v-model="confirmPassword"
        type="password"
        placeholder="再次输入密码"
        autocomplete="new-password"
        class="w-full px-4 py-2.5 border rounded-xl text-[15px] focus:outline-none focus:ring-1 transition-all"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)' }"
      />
    </div>

    <div
      v-if="error"
      class="px-3 py-2 text-sm rounded-lg border"
      :style="{ background: 'var(--error-subtle)', color: 'var(--error-emphasis)', borderColor: 'var(--error-subtle)' }"
    >{{ error }}</div>

    <div class="flex gap-2">
      <button
        type="submit"
        :disabled="loading"
        class="flex-1 py-2.5 text-white text-[15px] font-medium rounded-xl disabled:opacity-50 transition-colors"
        :style="{ background: 'var(--primary)' }"
      >
        {{ loading ? '注册中...' : '注册' }}
      </button>
      <button
        type="button"
        @click="$emit('switchToLogin')"
        class="px-4 py-2.5 text-[15px] font-medium rounded-xl border transition-colors"
        :style="{ borderColor: 'var(--border)', color: 'var(--text)' }"
      >
        返回登录
      </button>
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'
import { useAuth } from '../../composables/useAuth'

defineEmits(['switchToLogin'])

const { register } = useAuth()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  if (!username.value || !password.value) {
    error.value = '用户名和密码不能为空'
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  error.value = ''
  loading.value = true
  try {
    await register(username.value, password.value)
  } catch (e) {
    error.value = e.response?.data?.detail || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>
```

**Step 2: 提交**

```bash
git add frontend/src/components/auth/RegisterForm.vue
git commit -m "feat(auth): 新增 RegisterForm.vue 子组件"
```

---

## Task 16: `LoginPage.vue` 改为 shell（mode 切换）

**Files:**
- Modify: `frontend/src/components/LoginPage.vue`

**Step 1: 整体替换为 shell**

```vue
<template>
  <div class="h-screen flex items-center justify-center" :style="{ background: 'var(--surface)' }">
    <div class="w-full max-w-sm px-6">
      <div class="flex flex-col items-center mb-8">
        <div class="w-12 h-12 rounded-2xl flex items-center justify-center mb-4" :style="{ background: 'var(--text)' }">
          <FileSpreadsheet class="w-6 h-6 text-white" />
        </div>
        <h1 class="text-xl font-semibold" :style="{ color: 'var(--text)' }">Excel Agent</h1>
        <p class="text-sm mt-1" :style="{ color: 'var(--text-muted)' }">
          {{ mode === 'login' ? '登录以继续' : '创建新账号' }}
        </p>
      </div>

      <LoginForm
        v-if="mode === 'login'"
        :allow-registration="allowRegistration"
        @switchToRegister="mode = 'register'"
      />
      <RegisterForm
        v-else
        @switchToLogin="mode = 'login'"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { FileSpreadsheet } from 'lucide-vue-next'
import LoginForm from './auth/LoginForm.vue'
import RegisterForm from './auth/RegisterForm.vue'
import { getAuthConfig } from '../api'

const mode = ref('login')
const allowRegistration = ref(false)

onMounted(async () => {
  try {
    const cfg = await getAuthConfig()
    allowRegistration.value = cfg.allow_registration
  } catch {
    allowRegistration.value = false
  }
})
</script>
```

**Step 2: build 验证**

```bash
cd ~/Desktop/Excel/frontend
npm run build
```

Expected: build 通过

**Step 3: 提交**

```bash
git add frontend/src/components/LoginPage.vue
git commit -m "feat(auth): LoginPage 改为 shell，支持登录/注册模式切换"
```

---

## Task 17: `UserListRow.vue` 新建

**Files:**
- Create: `frontend/src/components/settings/UserListRow.vue`

**Step 1: 创建文件**

```vue
<template>
  <div
    class="flex items-center gap-2 px-3.5 py-2.5 rounded-lg text-[14px]"
    :style="{ background: 'var(--background)' }"
  >
    <span class="flex-1" :style="{ color: 'var(--text)' }">{{ user.username }}</span>

    <span
      v-if="user.is_admin"
      class="text-[11px] font-medium px-2 py-0.5 rounded"
      :style="{ background: 'var(--warning-subtle)', color: 'var(--warning-emphasis)' }"
    >管理员</span>

    <span
      v-if="!user.is_active"
      class="text-[11px] font-medium px-2 py-0.5 rounded"
      :style="{ background: 'var(--error-subtle)', color: 'var(--error-emphasis)' }"
    >已禁用</span>

    <template v-if="user.id !== currentUserId">
      <button
        @click="$emit('resetPassword', user)"
        class="text-[12px] px-2 py-1 rounded hover:opacity-80 transition-opacity"
        :style="{ color: 'var(--text-muted)' }"
        title="重置密码"
      >
        <Key class="w-3.5 h-3.5" />
      </button>
      <button
        @click="$emit('toggleActive', user)"
        class="text-[12px] px-2 py-1 rounded hover:opacity-80 transition-opacity"
        :style="{ color: user.is_active ? 'var(--warning-emphasis)' : 'var(--success-emphasis)' }"
        :title="user.is_active ? '禁用' : '启用'"
      >
        <component :is="user.is_active ? Lock : Unlock" class="w-3.5 h-3.5" />
      </button>
      <button
        @click="$emit('deleteUser', user.id)"
        class="text-[12px] px-2 py-1 rounded hover:opacity-80 transition-opacity"
        :style="{ color: 'var(--text-placeholder)' }"
        title="删除"
      >
        <Trash2 class="w-3.5 h-3.5" />
      </button>
    </template>
  </div>
</template>

<script setup>
import { Key, Lock, Unlock, Trash2 } from 'lucide-vue-next'

defineProps({
  user: { type: Object, required: true },
  currentUserId: { type: [String, Number], default: null }
})
defineEmits(['resetPassword', 'toggleActive', 'deleteUser'])
</script>
```

**Step 2: 提交**

```bash
git add frontend/src/components/settings/UserListRow.vue
git commit -m "feat(auth): UserListRow.vue 单行用户展示 + 操作按钮"
```

---

## Task 18: `AdminResetPasswordModal.vue` 新建

**Files:**
- Create: `frontend/src/components/settings/AdminResetPasswordModal.vue`

**Step 1: 创建文件**

```vue
<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    @click.self="$emit('cancel')"
  >
    <div class="rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden" :style="{ background: 'var(--surface)' }">
      <div class="px-6 pt-5 pb-2">
        <h3 class="text-base font-semibold" :style="{ color: 'var(--text)' }">重置密码</h3>
        <p class="text-sm mt-1" :style="{ color: 'var(--text-muted)' }">
          即将把 <strong :style="{ color: 'var(--text)' }">{{ username }}</strong> 的密码重置。请输入两次新密码确认。
        </p>
      </div>

      <div class="px-6 py-3 space-y-3">
        <input
          v-model="newPassword"
          type="password"
          placeholder="新密码"
          autocomplete="new-password"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none border"
          :style="{ borderColor: 'var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        />
        <input
          v-model="confirmPassword"
          type="password"
          placeholder="再次输入新密码"
          autocomplete="new-password"
          class="w-full px-3 py-2.5 rounded-lg text-[14px] focus:outline-none border"
          :style="{ borderColor: 'var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
        />
        <div
          v-if="error"
          class="px-3 py-2 text-[13px] rounded-lg"
          :style="{ background: 'var(--error-subtle)', color: 'var(--error-emphasis)' }"
        >{{ error }}</div>
      </div>

      <div class="flex justify-end gap-2 px-6 py-4 border-t" :style="{ borderColor: 'var(--border)' }">
        <button
          @click="$emit('cancel')"
          class="px-4 py-2 text-sm rounded-lg transition-colors"
          :style="{ color: 'var(--text-muted)' }"
        >取消</button>
        <button
          @click="handleConfirm"
          :disabled="!newPassword || loading"
          class="px-4 py-2 text-sm text-white rounded-lg transition-colors disabled:opacity-50"
          :style="{ background: 'var(--primary)' }"
        >{{ loading ? '提交中...' : '确认重置' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  username: { type: String, required: true },
  loading: { type: Boolean, default: false }
})
const emit = defineEmits(['confirm', 'cancel'])

const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')

function handleConfirm() {
  if (!newPassword.value) {
    error.value = '新密码不能为空'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = '两次输入的新密码不一致'
    return
  }
  error.value = ''
  emit('confirm', newPassword.value)
}
</script>
```

**Step 2: 提交**

```bash
git add frontend/src/components/settings/AdminResetPasswordModal.vue
git commit -m "feat(auth): AdminResetPasswordModal 管理员重置密码弹窗"
```

---

## Task 19: `UserManagement.vue` 重构

**Files:**
- Modify: `frontend/src/components/settings/UserManagement.vue`

**理念**：管理操作 API 调用放在 UserManagement 内部（它本来就负责用户列表），对父组件只暴露两个事件：`addUser`（父组件已有逻辑，保留）和 `refresh`（操作完成后请父重载列表）。这样避免 `emit` 无法 `await` 的异步 bug。

**Step 1: 完整替换**

```vue
<template>
  <section class="space-y-5">
    <div class="flex items-center gap-2">
      <Users class="w-[18px] h-[18px]" :style="{ color: 'var(--primary)' }" />
      <h2 class="text-base font-semibold" :style="{ color: 'var(--text)' }">用户管理</h2>
      <span
        class="text-[11px] font-medium px-2 py-0.5 rounded"
        :style="{ background: 'var(--primary-muted)', color: 'var(--primary)' }"
      >仅管理员</span>
    </div>

    <!-- 用户列表 -->
    <div class="space-y-1 max-w-md">
      <UserListRow
        v-for="u in users"
        :key="u.id"
        :user="u"
        :current-user-id="currentUserId"
        @resetPassword="onResetPassword"
        @toggleActive="handleToggleActive"
        @deleteUser="(id) => $emit('deleteUser', id)"
      />
    </div>

    <!-- 添加用户 -->
    <div class="flex gap-2 max-w-md">
      <input
        v-model="newUsername"
        placeholder="用户名"
        class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none border"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
      />
      <input
        v-model="newPassword"
        type="password"
        placeholder="密码"
        class="flex-1 px-3 py-2.5 rounded-lg text-[14px] focus:outline-none border"
        :style="{ borderColor: 'var(--input-border)', color: 'var(--text)', background: 'var(--surface)' }"
      />
      <button
        @click="handleAdd"
        :disabled="!newUsername || !newPassword"
        class="px-4 py-2.5 text-[14px] font-medium text-white rounded-lg disabled:opacity-50 transition-colors"
        :style="{ background: 'var(--text)' }"
      >添加</button>
    </div>

    <div v-if="error || localError" class="text-[13px]" :style="{ color: 'var(--error-emphasis)' }">
      {{ error || localError }}
    </div>

    <!-- 重置密码弹窗 -->
    <AdminResetPasswordModal
      v-if="resetTarget"
      :username="resetTarget.username"
      :loading="resetLoading"
      @confirm="handleResetConfirm"
      @cancel="resetTarget = null"
    />
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { Users } from 'lucide-vue-next'
import UserListRow from './UserListRow.vue'
import AdminResetPasswordModal from './AdminResetPasswordModal.vue'
import { adminResetPassword, setUserActive } from '../../api'

defineProps({
  users: { type: Array, default: () => [] },
  currentUserId: { type: [String, Number], default: null },
  error: { type: String, default: '' }
})

const emit = defineEmits(['addUser', 'deleteUser', 'refresh'])

const newUsername = ref('')
const newPassword = ref('')
const resetTarget = ref(null)
const resetLoading = ref(false)
const localError = ref('')

function handleAdd() {
  emit('addUser', { username: newUsername.value, password: newPassword.value })
  newUsername.value = ''
  newPassword.value = ''
}

function onResetPassword(user) {
  localError.value = ''
  resetTarget.value = user
}

async function handleResetConfirm(newPw) {
  resetLoading.value = true
  try {
    await adminResetPassword(resetTarget.value.id, newPw)
    resetTarget.value = null
  } catch (e) {
    localError.value = e.response?.data?.detail || '重置密码失败'
  } finally {
    resetLoading.value = false
  }
}

async function handleToggleActive({ userId, isActive }) {
  localError.value = ''
  try {
    await setUserActive(userId, isActive)
    emit('refresh')
  } catch (e) {
    localError.value = e.response?.data?.detail || '操作失败'
  }
}
</script>
```

**Step 2: build 验证**

```bash
cd ~/Desktop/Excel/frontend && npm run build
```

Expected: 通过

**Step 3: 提交**

```bash
git add frontend/src/components/settings/UserManagement.vue
git commit -m "feat(auth): UserManagement 接入 UserListRow + 重置密码弹窗 + 禁用切换"
```

---

## Task 20: `RegistrationToggle.vue` 新建

**Files:**
- Create: `frontend/src/components/settings/RegistrationToggle.vue`

**Step 1: 创建**

```vue
<template>
  <section class="space-y-5">
    <div class="flex items-center gap-2">
      <UserPlus class="w-[18px] h-[18px]" :style="{ color: 'var(--primary)' }" />
      <h2 class="text-base font-semibold" :style="{ color: 'var(--text)' }">开放注册</h2>
      <span
        class="text-[11px] font-medium px-2 py-0.5 rounded"
        :style="{ background: 'var(--primary-muted)', color: 'var(--primary)' }"
      >仅管理员</span>
    </div>

    <label class="flex items-center gap-3 max-w-md cursor-pointer">
      <input
        type="checkbox"
        :checked="modelValue"
        @change="$emit('update:modelValue', $event.target.checked)"
        class="w-4 h-4 accent-[color:var(--primary)]"
      />
      <div>
        <div class="text-[14px]" :style="{ color: 'var(--text)' }">允许新用户自行注册</div>
        <div class="text-[12px] mt-0.5" :style="{ color: 'var(--text-muted)' }">
          关闭后，登录页不再显示注册入口
        </div>
      </div>
    </label>
  </section>
</template>

<script setup>
import { UserPlus } from 'lucide-vue-next'

defineProps({ modelValue: { type: Boolean, default: true } })
defineEmits(['update:modelValue'])
</script>
```

**Step 2: 提交**

```bash
git add frontend/src/components/settings/RegistrationToggle.vue
git commit -m "feat(auth): RegistrationToggle.vue 注册开关组件"
```

---

## Task 21: `SettingsPage.vue` 接入新功能

**Files:**
- Modify: `frontend/src/components/SettingsPage.vue`

**Step 1: 修改导入**

```js
import {
  getSettings, updateSettings,
  listUsers, createUser, deleteUser, changePassword,
  getAuthConfig, setAuthConfig,
} from '../api'
```

加：

```js
import RegistrationToggle from './settings/RegistrationToggle.vue'
```

**Step 2: 模板里加 RegistrationToggle section（管理员可见）**

在 `<UserManagement>` 之前插入：

```vue
<RegistrationToggle
  v-if="isAdmin"
  v-model="allowRegistration"
  @update:modelValue="handleToggleRegistration"
/>
<div v-if="isAdmin" class="h-px" style="background: var(--border)" />
```

**Step 3: UserManagement 新增 refresh 事件绑定**

```vue
<UserManagement
  v-if="isAdmin"
  :users="userList"
  :currentUserId="currentUser?.id"
  :error="userError"
  @addUser="handleAddUser"
  @deleteUser="handleDeleteUser"
  @refresh="loadUsers"
/>
```

**Step 4: 脚本逻辑**

在 `<script setup>` 里补：

```js
const allowRegistration = ref(true)

async function loadAuthConfig() {
  if (!isAdmin.value) return
  try {
    const cfg = await getAuthConfig()
    allowRegistration.value = cfg.allow_registration
  } catch { /* 静默 */ }
}

async function handleToggleRegistration(val) {
  try {
    await setAuthConfig(val)
    allowRegistration.value = val
  } catch (e) {
    allowRegistration.value = !val  // 回滚 UI
  }
}
```

改 `onMounted`：

```js
onMounted(() => {
  loadSettings()
  loadUsers()
  loadAuthConfig()
})
```

**注意**：`handleDeleteUser` 已有，删除后也需 `loadUsers`，原代码已有这个行为，无需改动。

**Step 5: build 验证**

```bash
cd ~/Desktop/Excel/frontend && npm run build
```

Expected: 通过

**Step 6: 提交**

```bash
git add frontend/src/components/SettingsPage.vue
git commit -m "feat(auth): SettingsPage 接入注册开关 + 用户管理新动作"
```

---

## Task 22: 端到端浏览器验证

**目标**：在 NAS 部署前，本地打开 dev server 全流程走一遍。

**Step 1: 启动后端**

```bash
cd ~/Desktop/Excel/backend
DB_DIR=/tmp/exceldev JWT_SECRET=test-secret uvicorn main:app --port 8910 --reload
```

**Step 2: 启动前端 dev server**

另一终端：

```bash
cd ~/Desktop/Excel/frontend
# 确保 vite 代理到 8910（查看 vite.config.js）
npm run dev
```

**Step 3: 浏览器验证清单**

访问 http://localhost:5173（或 vite 实际端口）

- [ ] 登录页右侧出现"注册"按钮
- [ ] 点击"注册"进入注册表单，含"返回登录"按钮
- [ ] 注册：输入用户名 / 密码 / 确认密码，点击"注册" → 进入首页
- [ ] 不一致密码提示"两次输入的密码不一致"
- [ ] 重复用户名提示"用户名已存在"
- [ ] 退出后用 admin / admin123 登录
- [ ] 设置页管理员区出现：开放注册开关 / 用户管理
- [ ] 关闭注册开关 → 退出 → 登录页"注册"按钮消失
- [ ] 重开注册开关
- [ ] 用户管理：每个非自己行有 重置密码 / 禁用 / 删除 三按钮
- [ ] 点"重置密码" → 弹窗 → 输两次新密码 → 确认 → 该用户能用新密码登录
- [ ] 两次密码不一致时弹窗报错
- [ ] 点"禁用" → 该用户标记"已禁用"→ 该用户登录失败"账号已被禁用"
- [ ] 点"启用"恢复
- [ ] 在其他浏览器登录该用户，然后管理员禁用该账号 → 被禁用浏览器下次请求（例如切换对话）立即被踢回登录页

**Step 4: 30 分钟 idle 验证（压缩时间）**

因为等待 30 分钟不现实，用"token 被构造成 1 分钟后过期"模拟：

```bash
# 临时把 JWT_EXPIRE_MINUTES 改 1，重启，登录，空等 1 分 10 秒，触发任意请求（点用户管理刷新）
```

Expected: 应被 401 踢回登录页

**Step 5: 滑动刷新验证**

```bash
# 再把 JWT_EXPIRE_MINUTES 改 10（>REFRESH_THRESHOLD=15 不成立，改成 10 分钟）
# 阈值也要改，或者改 REFRESH_THRESHOLD_SECONDS=60（1 分钟内刷新）
```

改 `REFRESH_THRESHOLD_SECONDS=60` 后重启，登录，连续操作，打开浏览器 DevTools Network 看任意请求的响应头，等 token 剩余 <60 秒时应看到 `X-New-Token` 响应头，且 localStorage 中 token 被更新。

**Step 6: 验证完成后恢复常量**

把 `JWT_EXPIRE_MINUTES=30`、`REFRESH_THRESHOLD_SECONDS=15*60` 还原。

**Step 7: 无需提交**（只是验证）

---

## Task 23: 部署到 NAS

**Files:** 无本地修改

**说明**：Dockerfile stage 1 在容器内重新 `npm run build` 前端，所以不需要 scp `backend/static`。只需 scp 改动的源文件；Docker build 时会重新构建。

**Step 1: scp 改动的后端源文件 + 前端源文件到 NAS**

按 CLAUDE.md 部署规范：

```bash
cd ~/Desktop/Excel
# 后端 3 个文件
sshpass -p 'theendqq123' scp backend/app/api/auth.py admin@192.168.124.3:/home/admin/excel/backend/app/api/auth.py
sshpass -p 'theendqq123' scp backend/app/database.py admin@192.168.124.3:/home/admin/excel/backend/app/database.py
sshpass -p 'theendqq123' scp backend/main.py admin@192.168.124.3:/home/admin/excel/backend/main.py

# 前端源文件：组件、api、composable
sshpass -p 'theendqq123' scp frontend/src/api/index.js admin@192.168.124.3:/home/admin/excel/frontend/src/api/index.js
sshpass -p 'theendqq123' scp frontend/src/composables/useAuth.js admin@192.168.124.3:/home/admin/excel/frontend/src/composables/useAuth.js
sshpass -p 'theendqq123' scp frontend/src/components/LoginPage.vue admin@192.168.124.3:/home/admin/excel/frontend/src/components/LoginPage.vue
sshpass -p 'theendqq123' scp frontend/src/components/SettingsPage.vue admin@192.168.124.3:/home/admin/excel/frontend/src/components/SettingsPage.vue
sshpass -p 'theendqq123' scp -r frontend/src/components/auth admin@192.168.124.3:/home/admin/excel/frontend/src/components/
sshpass -p 'theendqq123' scp frontend/src/components/settings/UserManagement.vue admin@192.168.124.3:/home/admin/excel/frontend/src/components/settings/UserManagement.vue
sshpass -p 'theendqq123' scp frontend/src/components/settings/UserListRow.vue admin@192.168.124.3:/home/admin/excel/frontend/src/components/settings/UserListRow.vue
sshpass -p 'theendqq123' scp frontend/src/components/settings/AdminResetPasswordModal.vue admin@192.168.124.3:/home/admin/excel/frontend/src/components/settings/AdminResetPasswordModal.vue
sshpass -p 'theendqq123' scp frontend/src/components/settings/RegistrationToggle.vue admin@192.168.124.3:/home/admin/excel/frontend/src/components/settings/RegistrationToggle.vue
```

**Step 2: NAS 上重建**

```bash
sshpass -p 'theendqq123' ssh admin@192.168.124.3 "cd /home/admin/excel && echo 'theendqq123' | sudo -S docker compose up -d --build"
```

**Step 5: 生产验证**

浏览器访问 http://192.168.124.3:8910：

- [ ] 登录页"注册"按钮出现
- [ ] admin 登录
- [ ] 设置页：开放注册开关、用户管理三动作按钮完整

**Step 6: 最终提交**

```bash
cd ~/Desktop/Excel
git log --oneline -20  # 确认所有变更已提交
```

---

## 完成标准

- ✅ 后端 10 个 curl 端点测试通过（Task 1-11）
- ✅ 前端 `npm run build` 零错误
- ✅ 浏览器端到端 checklist 全过（Task 22）
- ✅ NAS 部署后生产环境可用（Task 23）
- ✅ 所有组件模板 <150 行
- ✅ 所有硬编码颜色用 CSS 变量
- ✅ 所有 commit 中文说明

## 后续可能的扩展（YAGNI 不做）

- 密码强度策略（用户已选 C：无要求）
- 邮箱验证 / 找回密码
- 管理员可改 `is_admin` 标记
- 审计日志 / 操作记录
- 频率限制（防注册滥用）

from __future__ import annotations

import os
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..database import get_db, get_setting, set_setting

router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_SECRET = os.environ.get("JWT_SECRET", "excel-agent-secret-change-me")
JWT_EXPIRE_MINUTES = 30


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class AuthConfigRequest(BaseModel):
    allow_registration: bool


class RegisterRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    new_password: str


class SetActiveRequest(BaseModel):
    is_active: bool


def create_token(user_id: int, username: str, is_admin: bool) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "is_admin": is_admin,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


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


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(403, "需要管理员权限")
    return user


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


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"user": user}


@router.post("/users")
async def create_user(req: CreateUserRequest, admin: dict = Depends(require_admin)):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (req.username,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(400, "用户名已存在")

    pw_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
        (req.username, pw_hash, req.is_admin),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, username, is_admin, is_active, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return {"users": [dict(r) for r in rows]}


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: dict = Depends(require_admin)):
    if user_id == admin["user_id"]:
        raise HTTPException(400, "不能删除自己")
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest, user: dict = Depends(get_current_user)
):
    conn = get_db()
    row = conn.execute(
        "SELECT password_hash FROM users WHERE id = ?", (user["user_id"],)
    ).fetchone()
    if not row or not bcrypt.checkpw(req.old_password.encode(), row["password_hash"].encode()):
        conn.close()
        raise HTTPException(400, "原密码错误")

    new_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, user["user_id"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/config")
async def get_auth_config():
    """公开的认证配置，用于登录页决定是否显示注册入口"""
    allow = get_setting("allow_registration", "true") == "true"
    return {"allow_registration": allow}


@router.put("/config")
async def update_auth_config(
    req: AuthConfigRequest, admin: dict = Depends(require_admin)
):
    set_setting("allow_registration", "true" if req.allow_registration else "false")
    return {"ok": True}


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

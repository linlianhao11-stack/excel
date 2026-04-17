from __future__ import annotations

import os
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..database import get_db

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


def create_token(user_id: int, username: str, is_admin: bool) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "is_admin": is_admin,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_current_user(request: Request) -> dict:
    """FastAPI 依赖：从 Authorization header 解析当前用户"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的登录凭证")


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(403, "需要管理员权限")
    return user


@router.post("/login")
async def login(req: LoginRequest):
    conn = get_db()
    row = conn.execute(
        "SELECT id, username, password_hash, is_admin FROM users WHERE username = ?",
        (req.username,),
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(401, "用户名或密码错误")

    if not bcrypt.checkpw(req.password.encode(), row["password_hash"].encode()):
        raise HTTPException(401, "用户名或密码错误")

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
        "SELECT id, username, is_admin, created_at FROM users"
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

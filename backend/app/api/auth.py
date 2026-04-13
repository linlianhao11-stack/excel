from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(req: LoginRequest):
    if not AUTH_PASSWORD:
        return {"ok": True}
    if req.password != AUTH_PASSWORD:
        raise HTTPException(401, "密码错误")
    return {"ok": True}

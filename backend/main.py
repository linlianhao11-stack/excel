from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI(title="Excel Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api.files import router as files_router
from app.api.chat import router as chat_router
from app.api.download import router as download_router
from app.api.auth import router as auth_router

app.include_router(files_router)
app.include_router(chat_router)
app.include_router(download_router)
app.include_router(auth_router)


@app.on_event("startup")
async def startup():
    from app.services.cleanup import cleanup_old_files

    asyncio.create_task(cleanup_old_files())


# 生产模式下托管前端静态文件（必须放最后，否则会拦截 /api 路由）
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

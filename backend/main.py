from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

# ── 日志配置 ──
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
# httpx / httpcore 太吵，只打 WARNING
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("excel-agent")

app = FastAPI(title="Excel Agent")

# CORS: 收紧来源
allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from app.api.files import router as files_router
from app.api.chat import router as chat_router
from app.api.download import router as download_router
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.settings import router as settings_router
from app.api.diff import router as diff_router

app.include_router(auth_router)
app.include_router(files_router)
app.include_router(chat_router)
app.include_router(download_router)
app.include_router(conversations_router)
app.include_router(settings_router)
app.include_router(diff_router)


@app.on_event("startup")
async def startup():
    from app.database import init_db
    init_db()
    logger.info("数据库初始化完成")
    logger.info("LOG_LEVEL=%s", LOG_LEVEL)

    # 启动文件清理任务
    from app.services.cleanup import cleanup_old_files
    asyncio.create_task(cleanup_old_files())


# 生产模式下托管前端静态文件（必须放最后，否则会拦截 /api 路由）
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

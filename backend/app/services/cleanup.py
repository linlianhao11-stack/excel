from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

WORK_DIR = Path(os.environ.get("WORK_DIR", "/data/work"))
MAX_AGE_DAYS = 7


async def cleanup_old_files():
    """清理超过 MAX_AGE_DAYS 天的文件"""
    while True:
        cutoff = time.time() - MAX_AGE_DAYS * 86400
        if WORK_DIR.exists():
            for f in WORK_DIR.iterdir():
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
        await asyncio.sleep(3600)

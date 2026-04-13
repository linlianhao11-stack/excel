# Excel Agent 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个 Docker 部署的 Web 工具，用户拖入 Excel 文件 + 自然语言描述需求，通过 DeepSeek API 生成 pandas 代码并本地执行，返回处理结果。

**Architecture:** FastAPI 后端提供文件管理、SSE 流式对话、Agent 多轮循环（DeepSeek 生成代码 → subprocess 沙箱执行 → 错误自愈）。Vue 3 + Tailwind 前端提供类 Claude 风格的聊天界面。单容器 Docker 部署，Nginx 托管前端静态文件并反代后端 API。

**Tech Stack:** Python 3.11 / FastAPI / pandas / openpyxl / SQLite (aiosqlite) / Vue 3 / Tailwind CSS 4 / Vite / Docker

---

### Task 1: 项目骨架 + Docker 基础

**Files:**
- Create: `backend/main.py`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `docker-compose.yml`
- Create: `Dockerfile`
- Create: `nginx.conf`
- Create: `.gitignore`
- Create: `.env.example`

**Step 1: 创建后端骨架**

`backend/requirements.txt`:
```
fastapi==0.115.12
uvicorn[standard]==0.34.2
python-multipart==0.0.20
pandas==2.1.4
openpyxl==3.1.2
aiosqlite==0.21.0
httpx==0.28.1
python-dotenv==1.1.0
```

`backend/main.py`:
```python
from __future__ import annotations

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

# API 路由后续注册
# app.include_router(...)

# 生产模式下托管前端静态文件
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
```

`backend/app/__init__.py`: 空文件

**Step 2: 创建前端骨架**

`frontend/package.json`:
```json
{
  "name": "excel-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "axios": "^1.8.4",
    "lucide-vue-next": "^0.509.0",
    "marked": "^15.0.7",
    "highlight.js": "^11.11.1"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.4",
    "vite": "^6.3.2",
    "tailwindcss": "^4.1.4",
    "@tailwindcss/vite": "^4.1.4",
    "autoprefixer": "^10.4.21"
  }
}
```

`frontend/vite.config.js`:
```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true
  }
})
```

`frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Excel Agent</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

`frontend/src/main.js`:
```javascript
import { createApp } from 'vue'
import App from './App.vue'
import './styles/main.css'

createApp(App).mount('#app')
```

`frontend/src/styles/main.css`:
```css
@import "tailwindcss";

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
```

`frontend/src/App.vue`:
```vue
<template>
  <div class="h-screen bg-gray-50 flex items-center justify-center">
    <p class="text-gray-500">Excel Agent - Loading...</p>
  </div>
</template>
```

**Step 3: 创建 Docker 配置**

`.env.example`:
```
DEEPSEEK_API_KEY=sk-xxx
AUTH_PASSWORD=excel123
```

`nginx.conf`:
```nginx
server {
    listen 80;
    server_name _;
    client_max_body_size 100M;

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;
        proxy_cache off;
    }

    location / {
        root /app/backend/static;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}
```

`Dockerfile`:
```dockerfile
FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /build/../backend/static ./backend/static/
COPY nginx.conf /etc/nginx/sites-enabled/default

RUN mkdir -p /data/work /data/db

EXPOSE 80

CMD nginx && uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

`docker-compose.yml`:
```yaml
services:
  app:
    build: .
    ports:
      - "8080:80"
    volumes:
      - excel_data:/data
    env_file:
      - .env
    restart: unless-stopped

volumes:
  excel_data:
```

`.gitignore`:
```
__pycache__/
*.pyc
node_modules/
backend/static/
.env
/data/
*.egg-info/
dist/
.vite/
```

**Step 4: 提交**

```bash
git add -A
git commit -m "feat: 项目骨架 - FastAPI + Vue 3 + Docker 配置"
```

---

### Task 2: 后端 - 文件上传与 Excel 预处理服务

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/excel.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/files.py`
- Modify: `backend/main.py`

**Step 1: 实现 ExcelService**

`backend/app/services/__init__.py`: 空文件

`backend/app/services/excel.py`:
```python
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd

WORK_DIR = Path(os.environ.get("WORK_DIR", "/data/work"))


def ensure_work_dir() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)


import os


def save_upload(filename: str, content: bytes) -> dict:
    """保存上传文件，返回文件信息"""
    ensure_work_dir()
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{filename}"
    file_path = WORK_DIR / safe_name
    file_path.write_bytes(content)
    profile = profile_excel(str(file_path))
    return {
        "file_id": file_id,
        "filename": filename,
        "path": str(file_path),
        "profile": profile,
    }


def profile_excel(path: str) -> dict[str, Any]:
    """分析 Excel 结构：sheet名、列名、类型、样本、行数"""
    xl = pd.ExcelFile(path)
    result = {}
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        sample_df = df.head(5)
        result[sheet] = {
            "columns": df.columns.tolist(),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "sample": sample_df.fillna("").to_dict("records"),
            "row_count": len(df),
            "col_count": len(df.columns),
        }
    return result


def build_context(files: list[dict], strategy: str = "auto") -> str:
    """根据文件 profile 构建给 LLM 的上下文描述"""
    parts = []
    for f in files:
        parts.append(f"## 文件: {f['filename']}")
        for sheet_name, info in f["profile"].items():
            total_rows = info["row_count"]
            parts.append(f"\n### Sheet: {sheet_name} ({total_rows} 行, {info['col_count']} 列)")
            parts.append(f"列: {info['columns']}")
            parts.append(f"类型: {info['dtypes']}")

            if strategy == "auto":
                if total_rows <= 200:
                    parts.append(f"数据(全量):\n{info['sample']}")
                else:
                    parts.append(f"样本(前5行):\n{info['sample']}")
                    parts.append("(AI 可用 query 工具探索更多数据)")
            elif strategy == "sample":
                parts.append(f"样本(前5行):\n{info['sample']}")
    return "\n".join(parts)
```

**Step 2: 实现文件上传 API**

`backend/app/api/__init__.py`: 空文件

`backend/app/api/files.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List

from ..services.excel import save_upload, WORK_DIR

router = APIRouter(prefix="/api/files", tags=["files"])

# 内存中存储已上传文件信息(MVP 够用，后期换 SQLite)
uploaded_files: dict[str, dict] = {}


@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    results = []
    for f in files:
        if not f.filename.endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(400, f"不支持的文件格式: {f.filename}")
        content = await f.read()
        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(400, f"文件过大: {f.filename}")
        info = save_upload(f.filename, content)
        uploaded_files[info["file_id"]] = info
        results.append(info)
    return {"files": results}


@router.get("/list")
async def list_files():
    return {"files": list(uploaded_files.values())}


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    info = uploaded_files.pop(file_id, None)
    if not info:
        raise HTTPException(404, "文件不存在")
    path = WORK_DIR / f"{file_id}_{info['filename']}"
    if path.exists():
        path.unlink()
    return {"ok": True}
```

**Step 3: 注册路由到 main.py**

在 `backend/main.py` 中添加:
```python
from app.api.files import router as files_router
app.include_router(files_router)
```

**Step 4: 提交**

```bash
git add -A
git commit -m "feat: 文件上传 API + Excel 预处理服务"
```

---

### Task 3: 后端 - LLM Provider 抽象 + DeepSeek 实现

**Files:**
- Create: `backend/app/services/llm.py`

**Step 1: 实现 LLMProvider**

`backend/app/services/llm.py`:
```python
from __future__ import annotations

import os
import json
from typing import AsyncGenerator

import httpx


class LLMProvider:
    """LLM 调用抽象基类"""

    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncGenerator[dict, None]:
        raise NotImplementedError
        yield  # noqa: make it a generator


class DeepSeekProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

    async def chat_stream(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncGenerator[dict, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.0,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"]
                        yield delta
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue


def get_llm_provider() -> LLMProvider:
    provider = os.environ.get("LLM_PROVIDER", "deepseek")
    if provider == "deepseek":
        return DeepSeekProvider()
    raise ValueError(f"未知的 LLM provider: {provider}")
```

**Step 2: 提交**

```bash
git add -A
git commit -m "feat: LLM Provider 抽象层 + DeepSeek 流式实现"
```

---

### Task 4: 后端 - 沙箱执行服务

**Files:**
- Create: `backend/app/services/sandbox.py`

**Step 1: 实现 SandboxService**

`backend/app/services/sandbox.py`:
```python
from __future__ import annotations

import ast
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

WORK_DIR = Path(os.environ.get("WORK_DIR", "/data/work"))
TIMEOUT = 30
MAX_OUTPUT_LEN = 5000

# 危险模块黑名单
BLOCKED_MODULES = {
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "urllib", "requests", "httpx",
    "importlib", "ctypes", "signal", "threading", "multiprocessing",
}


def check_code_safety(code: str) -> str | None:
    """AST 检查代码安全性，返回 None 表示安全，否则返回原因"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"语法错误: {e}"

    for node in ast.walk(tree):
        # 检查 import
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_MODULES:
                    return f"禁止导入模块: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in BLOCKED_MODULES:
                    return f"禁止导入模块: {node.module}"
        # 检查 __import__、exec、eval
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("__import__", "exec", "eval", "compile"):
                return f"禁止调用: {func.id}()"
            if isinstance(func, ast.Attribute) and func.attr in ("__import__", "system", "popen"):
                return f"禁止调用: .{func.attr}()"

    return None


def execute_code(code: str, file_paths: dict[str, str]) -> dict:
    """
    在子进程中执行代码。
    file_paths: {"INPUT_PATH": "/data/work/xxx.xlsx", "OUTPUT_PATH": "/data/work/result.xlsx"}
    返回: {"success": bool, "stdout": str, "stderr": str, "output_path": str | None}
    """
    # 安全检查
    safety = check_code_safety(code)
    if safety:
        return {"success": False, "stdout": "", "stderr": f"安全检查失败: {safety}", "output_path": None}

    # 准备输出路径
    output_id = uuid.uuid4().hex[:8]
    output_path = str(WORK_DIR / f"result_{output_id}.xlsx")

    # 构建完整脚本
    header = "import pandas as pd\nimport numpy as np\nimport re\nfrom datetime import datetime, timedelta\n\n"
    for var_name, var_path in file_paths.items():
        header += f'{var_name} = r"{var_path}"\n'
    header += f'OUTPUT_PATH = r"{output_path}"\n\n'

    full_code = header + code

    # 写入临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=str(WORK_DIR)) as f:
        f.write(full_code)
        script_path = f.name

    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=str(WORK_DIR),
            env={
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin"),
                "HOME": "/tmp",
                "PYTHONPATH": "",
            },
        )
        stdout = result.stdout[:MAX_OUTPUT_LEN]
        stderr = result.stderr[:MAX_OUTPUT_LEN]
        success = result.returncode == 0

        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "output_path": output_path if success and Path(output_path).exists() else None,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"执行超时 ({TIMEOUT}秒)",
            "output_path": None,
        }
    finally:
        Path(script_path).unlink(missing_ok=True)


def execute_query(code: str, file_paths: dict[str, str]) -> dict:
    """执行只读查询代码，返回 print 输出。用于 Agent 探索数据。"""
    # 在代码末尾不生成文件，只返回 stdout
    header = "import pandas as pd\nimport numpy as np\nimport re\nfrom datetime import datetime, timedelta\n\n"
    for var_name, var_path in file_paths.items():
        header += f'{var_name} = r"{var_path}"\n'
    header += "\n"

    full_code = header + code

    safety = check_code_safety(full_code)
    if safety:
        return {"success": False, "output": f"安全检查失败: {safety}"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=str(WORK_DIR)) as f:
        f.write(full_code)
        script_path = f.name

    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=str(WORK_DIR),
            env={
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin"),
                "HOME": "/tmp",
                "PYTHONPATH": "",
            },
        )
        output = result.stdout[:MAX_OUTPUT_LEN]
        if result.returncode != 0:
            output = result.stderr[:MAX_OUTPUT_LEN]
        return {"success": result.returncode == 0, "output": output}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": f"查询超时 ({TIMEOUT}秒)"}
    finally:
        Path(script_path).unlink(missing_ok=True)
```

**Step 2: 提交**

```bash
git add -A
git commit -m "feat: 沙箱执行服务 - subprocess 隔离 + AST 安全检查"
```

---

### Task 5: 后端 - Agent 核心循环

**Files:**
- Create: `backend/app/services/agent.py`

**Step 1: 实现 AgentService**

`backend/app/services/agent.py`:
```python
from __future__ import annotations

import json
import re
from typing import AsyncGenerator

from .llm import get_llm_provider
from .sandbox import execute_code, execute_query
from .excel import build_context

SYSTEM_PROMPT = """你是一个 Excel 数据处理助手。用户会给你 Excel 文件的结构信息和处理需求。

你有两个工具可以使用：

1. **query** - 执行只读 Python 代码来探索数据（查看内容、统计、筛选等）
   参数: {"code": "python代码"}
   代码中可用变量: INPUT_PATH_1, INPUT_PATH_2, ... (每个上传文件一个)
   只需要 print() 输出你想看的内容

2. **execute** - 执行 Python 代码处理数据并生成结果文件
   参数: {"code": "python代码"}
   代码中可用变量: INPUT_PATH_1, INPUT_PATH_2, ..., OUTPUT_PATH
   必须将结果写入 OUTPUT_PATH

工作流程：
- 先用 query 探索数据，理解内容
- 确认理解后用 execute 生成结果
- 如果执行报错，分析原因后修复代码重试
- 每次只调用一个工具

可用的库：pandas, numpy, re, datetime, openpyxl
禁止使用：os, sys, subprocess, shutil 等系统模块

回复时请用中文，简洁说明你在做什么。"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query",
            "description": "执行只读 Python 代码探索数据，返回 print 输出",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要执行的 Python 代码"}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute",
            "description": "执行 Python 代码处理数据并生成结果文件到 OUTPUT_PATH",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "要执行的 Python 代码"}
                },
                "required": ["code"],
            },
        },
    },
]

MAX_TURNS = 10
MAX_RETRIES = 3


async def run_agent(
    user_message: str,
    files: list[dict],
) -> AsyncGenerator[dict, None]:
    """
    Agent 主循环，yield SSE 事件：
    - {"type": "text", "content": "..."} 文本流
    - {"type": "tool_call", "name": "query|execute", "code": "..."} 工具调用
    - {"type": "tool_result", "name": "...", "result": "..."} 工具结果
    - {"type": "done", "output_path": "..." | None} 完成
    - {"type": "error", "message": "..."} 错误
    """
    llm = get_llm_provider()

    # 构建文件路径映射
    file_paths = {}
    for i, f in enumerate(files, 1):
        file_paths[f"INPUT_PATH_{i}"] = f["path"]

    # 构建初始消息
    context = build_context(files)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"已上传的文件信息：\n\n{context}\n\n用户需求：{user_message}",
        },
    ]

    output_path = None
    retry_count = 0

    for turn in range(MAX_TURNS):
        # 收集完整的 assistant 回复
        full_content = ""
        tool_calls_data = {}  # id -> {name, arguments_str}
        current_tool_id = None

        async for delta in llm.chat_stream(messages, tools=TOOLS):
            # 文本内容
            if "content" in delta and delta["content"]:
                full_content += delta["content"]
                yield {"type": "text", "content": delta["content"]}

            # 工具调用
            if "tool_calls" in delta:
                for tc in delta["tool_calls"]:
                    tc_id = tc.get("id")
                    if tc_id:
                        current_tool_id = tc_id
                        tool_calls_data[tc_id] = {
                            "name": tc["function"]["name"],
                            "arguments_str": "",
                        }
                    if current_tool_id and "function" in tc:
                        args_chunk = tc["function"].get("arguments", "")
                        if args_chunk:
                            tool_calls_data[current_tool_id]["arguments_str"] += args_chunk

        # 没有工具调用，说明 AI 直接回复了，对话结束
        if not tool_calls_data:
            yield {"type": "done", "output_path": output_path}
            return

        # 处理工具调用
        assistant_msg = {"role": "assistant", "content": full_content or None, "tool_calls": []}
        for tc_id, tc_info in tool_calls_data.items():
            assistant_msg["tool_calls"].append({
                "id": tc_id,
                "type": "function",
                "function": {
                    "name": tc_info["name"],
                    "arguments": tc_info["arguments_str"],
                },
            })
        messages.append(assistant_msg)

        # 逐个执行工具
        for tc_id, tc_info in tool_calls_data.items():
            name = tc_info["name"]
            try:
                args = json.loads(tc_info["arguments_str"])
            except json.JSONDecodeError:
                tool_result = "参数解析失败"
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_result})
                yield {"type": "tool_result", "name": name, "result": tool_result}
                continue

            code = args.get("code", "")
            yield {"type": "tool_call", "name": name, "code": code}

            if name == "query":
                result = execute_query(code, file_paths)
                tool_result = result["output"] if result["success"] else f"错误: {result['output']}"
            elif name == "execute":
                result = execute_code(code, file_paths)
                if result["success"]:
                    output_path = result["output_path"]
                    tool_result = f"执行成功。输出文件: {output_path}"
                    if result["stdout"]:
                        tool_result += f"\n标准输出: {result['stdout']}"
                else:
                    retry_count += 1
                    tool_result = f"执行失败 (重试 {retry_count}/{MAX_RETRIES}): {result['stderr']}"
                    if retry_count >= MAX_RETRIES:
                        yield {"type": "error", "message": f"代码执行多次失败: {result['stderr']}"}
                        yield {"type": "done", "output_path": None}
                        return
            else:
                tool_result = f"未知工具: {name}"

            messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_result})
            yield {"type": "tool_result", "name": name, "result": tool_result}

    yield {"type": "error", "message": "达到最大对话轮数"}
    yield {"type": "done", "output_path": output_path}
```

**Step 2: 提交**

```bash
git add -A
git commit -m "feat: Agent 核心循环 - 多轮对话 + 工具调用 + 错误自愈"
```

---

### Task 6: 后端 - 聊天 SSE 接口 + 下载接口

**Files:**
- Create: `backend/app/api/chat.py`
- Create: `backend/app/api/download.py`
- Modify: `backend/main.py`

**Step 1: 实现聊天 SSE 接口**

`backend/app/api/chat.py`:
```python
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.agent import run_agent
from .files import uploaded_files

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    file_ids: list[str]


@router.post("/chat")
async def chat(req: ChatRequest):
    # 查找文件
    files = []
    for fid in req.file_ids:
        if fid not in uploaded_files:
            return StreamingResponse(
                iter([f"data: {json.dumps({'type': 'error', 'message': f'文件不存在: {fid}'})}\n\n"]),
                media_type="text/event-stream",
            )
        files.append(uploaded_files[fid])

    if not files:
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'message': '请先上传文件'})}\n\n"]),
            media_type="text/event-stream",
        )

    async def event_stream():
        try:
            async for event in run_agent(req.message, files):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**Step 2: 实现下载接口**

`backend/app/api/download.py`:
```python
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/download")
async def download_file(path: str):
    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    # 安全检查：只允许下载 work 目录下的文件
    if "/data/work" not in str(file_path.resolve()):
        raise HTTPException(403, "无权访问")
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

**Step 3: 注册路由**

`backend/main.py` 添加:
```python
from app.api.chat import router as chat_router
from app.api.download import router as download_router

app.include_router(chat_router)
app.include_router(download_router)
```

**Step 4: 提交**

```bash
git add -A
git commit -m "feat: 聊天 SSE 接口 + 文件下载接口"
```

---

### Task 7: 前端 - API 层 + 状态管理

**Files:**
- Create: `frontend/src/api/index.js`
- Create: `frontend/src/composables/useChat.js`
- Create: `frontend/src/composables/useFiles.js`

**Step 1: 实现 API 层**

`frontend/src/api/index.js`:
```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export async function uploadFiles(files) {
  const formData = new FormData()
  files.forEach(f => formData.append('files', f))
  const { data } = await api.post('/files/upload', formData)
  return data.files
}

export async function listFiles() {
  const { data } = await api.get('/files/list')
  return data.files
}

export async function deleteFile(fileId) {
  await api.delete(`/files/${fileId}`)
}

export function chatStream(message, fileIds, onEvent) {
  const controller = new AbortController()

  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, file_ids: fileIds }),
    signal: controller.signal,
  }).then(async (response) => {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            onEvent({ type: 'stream_end' })
            return
          }
          try {
            onEvent(JSON.parse(data))
          } catch {}
        }
      }
    }
  }).catch(err => {
    if (err.name !== 'AbortError') {
      onEvent({ type: 'error', message: err.message })
    }
  })

  return controller
}

export function getDownloadUrl(path) {
  return `/api/download?path=${encodeURIComponent(path)}`
}
```

**Step 2: 实现 useFiles composable**

`frontend/src/composables/useFiles.js`:
```javascript
import { ref } from 'vue'
import { uploadFiles as apiUpload, deleteFile as apiDelete } from '../api'

const files = ref([])
const uploading = ref(false)

export function useFiles() {
  async function upload(rawFiles) {
    uploading.value = true
    try {
      const newFiles = await apiUpload(rawFiles)
      files.value.push(...newFiles)
      return newFiles
    } finally {
      uploading.value = false
    }
  }

  async function remove(fileId) {
    await apiDelete(fileId)
    files.value = files.value.filter(f => f.file_id !== fileId)
  }

  function clear() {
    files.value = []
  }

  return { files, uploading, upload, remove, clear }
}
```

**Step 3: 实现 useChat composable**

`frontend/src/composables/useChat.js`:
```javascript
import { ref } from 'vue'
import { chatStream } from '../api'

const messages = ref([])
const streaming = ref(false)

export function useChat() {
  let controller = null

  function send(text, fileIds) {
    // 添加用户消息
    messages.value.push({ role: 'user', content: text })

    // 添加 assistant 占位
    const assistantMsg = {
      role: 'assistant',
      content: '',
      toolCalls: [],
      outputPath: null,
      error: null,
    }
    messages.value.push(assistantMsg)

    streaming.value = true

    controller = chatStream(text, fileIds, (event) => {
      switch (event.type) {
        case 'text':
          assistantMsg.content += event.content
          break
        case 'tool_call':
          assistantMsg.toolCalls.push({
            name: event.name,
            code: event.code,
            result: null,
          })
          break
        case 'tool_result':
          const lastCall = assistantMsg.toolCalls[assistantMsg.toolCalls.length - 1]
          if (lastCall) lastCall.result = event.result
          break
        case 'done':
          assistantMsg.outputPath = event.output_path
          streaming.value = false
          break
        case 'error':
          assistantMsg.error = event.message
          streaming.value = false
          break
        case 'stream_end':
          streaming.value = false
          break
      }
    })
  }

  function stop() {
    if (controller) controller.abort()
    streaming.value = false
  }

  function clearMessages() {
    messages.value = []
  }

  return { messages, streaming, send, stop, clearMessages }
}
```

**Step 4: 提交**

```bash
git add -A
git commit -m "feat: 前端 API 层 + useChat/useFiles composables"
```

---

### Task 8: 前端 - 主界面布局 (类 Claude 风格)

**Files:**
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/components/ChatPanel.vue`
- Create: `frontend/src/components/MessageBubble.vue`
- Create: `frontend/src/components/ChatInput.vue`

**Step 1: App.vue 主布局**

`frontend/src/App.vue`:
```vue
<template>
  <div class="h-screen flex flex-col bg-white">
    <!-- 顶栏 -->
    <header class="h-13 border-b border-gray-200 flex items-center px-4 shrink-0">
      <h1 class="text-base font-semibold text-gray-800">Excel Agent</h1>
      <div class="ml-auto flex items-center gap-2">
        <span
          v-for="f in files"
          :key="f.file_id"
          class="inline-flex items-center gap-1 px-2 py-0.5 bg-orange-50 text-orange-700 text-xs rounded-md border border-orange-200"
        >
          <FileSpreadsheet class="w-3 h-3" />
          {{ f.filename }}
          <button @click="remove(f.file_id)" class="ml-0.5 hover:text-orange-900">
            <X class="w-3 h-3" />
          </button>
        </span>
      </div>
    </header>

    <!-- 对话区 -->
    <ChatPanel />
  </div>
</template>

<script setup>
import { FileSpreadsheet, X } from 'lucide-vue-next'
import { useFiles } from './composables/useFiles'
import ChatPanel from './components/ChatPanel.vue'

const { files, remove } = useFiles()
</script>
```

**Step 2: ChatPanel.vue**

`frontend/src/components/ChatPanel.vue`:
```vue
<template>
  <div class="flex-1 flex flex-col min-h-0">
    <!-- 消息列表 -->
    <div ref="scrollContainer" class="flex-1 overflow-y-auto">
      <div class="max-w-3xl mx-auto py-8 px-4">
        <!-- 空状态 -->
        <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400 pt-32">
          <FileSpreadsheet class="w-10 h-10 mb-3 text-gray-300" />
          <p class="text-lg font-medium text-gray-500 mb-1">上传 Excel，告诉我你想做什么</p>
          <p class="text-sm">支持 .xlsx / .xls / .csv 格式</p>
        </div>

        <!-- 消息列表 -->
        <MessageBubble
          v-for="(msg, i) in messages"
          :key="i"
          :message="msg"
        />
      </div>
    </div>

    <!-- 输入区 -->
    <ChatInput @send="handleSend" />
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { FileSpreadsheet } from 'lucide-vue-next'
import { useChat } from '../composables/useChat'
import { useFiles } from '../composables/useFiles'
import MessageBubble from './MessageBubble.vue'
import ChatInput from './ChatInput.vue'

const { messages, streaming, send } = useChat()
const { files } = useFiles()
const scrollContainer = ref(null)

function handleSend(text) {
  const fileIds = files.value.map(f => f.file_id)
  send(text, fileIds)
}

// 自动滚动到底部
watch(
  () => messages.value.length && messages.value[messages.value.length - 1]?.content,
  async () => {
    await nextTick()
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  },
  { deep: true }
)
</script>
```

**Step 3: MessageBubble.vue**

`frontend/src/components/MessageBubble.vue`:
```vue
<template>
  <div :class="['mb-6', message.role === 'user' ? 'flex justify-end' : '']">
    <!-- 用户消息 -->
    <div
      v-if="message.role === 'user'"
      class="max-w-lg px-4 py-2.5 bg-gray-100 rounded-2xl text-gray-800 text-sm leading-relaxed"
    >
      {{ message.content }}
    </div>

    <!-- AI 消息 -->
    <div v-else class="space-y-3">
      <!-- 文本内容 -->
      <div
        v-if="message.content"
        class="text-sm text-gray-800 leading-relaxed prose prose-sm max-w-none"
        v-html="renderMarkdown(message.content)"
      />

      <!-- 工具调用 -->
      <div
        v-for="(tc, i) in message.toolCalls"
        :key="i"
        class="border border-gray-200 rounded-lg overflow-hidden text-xs"
      >
        <div
          class="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border-b border-gray-200 cursor-pointer select-none"
          @click="tc._expanded = !tc._expanded"
        >
          <component :is="tc.name === 'query' ? Search : Play" class="w-3.5 h-3.5 text-gray-500" />
          <span class="font-medium text-gray-600">{{ tc.name === 'query' ? '探索数据' : '执行代码' }}</span>
          <ChevronDown :class="['w-3.5 h-3.5 text-gray-400 ml-auto transition-transform', tc._expanded ? 'rotate-180' : '']" />
        </div>
        <div v-show="tc._expanded" class="divide-y divide-gray-100">
          <pre class="px-3 py-2 bg-gray-950 text-gray-100 overflow-x-auto"><code>{{ tc.code }}</code></pre>
          <pre v-if="tc.result" class="px-3 py-2 bg-white text-gray-600 overflow-x-auto whitespace-pre-wrap">{{ tc.result }}</pre>
        </div>
      </div>

      <!-- 下载按钮 -->
      <a
        v-if="message.outputPath"
        :href="getDownloadUrl(message.outputPath)"
        class="inline-flex items-center gap-2 px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-sm rounded-lg transition-colors"
      >
        <Download class="w-4 h-4" />
        下载结果文件
      </a>

      <!-- 错误 -->
      <div v-if="message.error" class="px-3 py-2 bg-red-50 text-red-600 text-sm rounded-lg border border-red-200">
        {{ message.error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { Search, Play, Download, ChevronDown } from 'lucide-vue-next'
import { marked } from 'marked'
import { getDownloadUrl } from '../api'

defineProps({ message: Object })

function renderMarkdown(text) {
  return marked.parse(text, { breaks: true })
}
</script>
```

**Step 4: ChatInput.vue**

`frontend/src/components/ChatInput.vue`:
```vue
<template>
  <div class="border-t border-gray-200 bg-white px-4 py-3">
    <div class="max-w-3xl mx-auto">
      <div
        class="flex items-end gap-2 border border-gray-300 rounded-2xl px-3 py-2 focus-within:border-gray-400 focus-within:ring-1 focus-within:ring-gray-400 transition-all"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleDrop"
        :class="{ 'border-orange-400 bg-orange-50/50': dragOver }"
      >
        <!-- 上传按钮 -->
        <button
          @click="$refs.fileInput.click()"
          class="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors shrink-0"
        >
          <Paperclip class="w-5 h-5" />
        </button>
        <input
          ref="fileInput"
          type="file"
          multiple
          accept=".xlsx,.xls,.csv"
          class="hidden"
          @change="handleFileSelect"
        />

        <!-- 文本输入 -->
        <textarea
          ref="textareaRef"
          v-model="text"
          @keydown.enter.exact.prevent="handleSend"
          @input="autoResize"
          rows="1"
          placeholder="描述你想对 Excel 做什么..."
          class="flex-1 resize-none bg-transparent text-sm text-gray-800 placeholder-gray-400 focus:outline-none max-h-40 leading-relaxed py-1"
        />

        <!-- 发送按钮 -->
        <button
          @click="handleSend"
          :disabled="!canSend"
          :class="[
            'p-1.5 rounded-lg transition-colors shrink-0',
            canSend ? 'bg-gray-800 text-white hover:bg-gray-700' : 'bg-gray-200 text-gray-400'
          ]"
        >
          <ArrowUp class="w-5 h-5" />
        </button>
      </div>

      <!-- 拖拽提示 -->
      <p v-if="dragOver" class="text-xs text-orange-500 mt-1.5 text-center">松开即可上传文件</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Paperclip, ArrowUp } from 'lucide-vue-next'
import { useFiles } from '../composables/useFiles'
import { useChat } from '../composables/useChat'

const emit = defineEmits(['send'])

const { files, upload } = useFiles()
const { streaming } = useChat()

const text = ref('')
const dragOver = ref(false)
const textareaRef = ref(null)

const canSend = computed(() => text.value.trim() && files.value.length > 0 && !streaming.value)

function handleSend() {
  if (!canSend.value) return
  emit('send', text.value.trim())
  text.value = ''
  if (textareaRef.value) textareaRef.value.style.height = 'auto'
}

function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = el.scrollHeight + 'px'
}

async function handleDrop(e) {
  dragOver.value = false
  const droppedFiles = Array.from(e.dataTransfer.files).filter(f =>
    f.name.endsWith('.xlsx') || f.name.endsWith('.xls') || f.name.endsWith('.csv')
  )
  if (droppedFiles.length) await upload(droppedFiles)
}

async function handleFileSelect(e) {
  const selected = Array.from(e.target.files)
  if (selected.length) await upload(selected)
  e.target.value = ''
}
</script>
```

**Step 5: 提交**

```bash
git add -A
git commit -m "feat: 前端 Claude 风格聊天界面 - 消息气泡 + 代码展示 + 拖拽上传"
```

---

### Task 9: 集成测试 + 修复

**Step 1: 本地启动后端验证**

```bash
cd backend && pip install -r requirements.txt
WORK_DIR=/tmp/excel_work DEEPSEEK_API_KEY=test uvicorn main:app --reload --port 8000
```

验证: `curl http://localhost:8000/docs` 返回 Swagger UI

**Step 2: 本地启动前端验证**

```bash
cd frontend && npm install && npm run dev
```

验证: 浏览器打开 http://localhost:3000 能看到界面

**Step 3: 端到端测试**

1. 拖入一个测试 Excel
2. 输入 "统计每列的数据量"
3. 验证 SSE 流式输出正常
4. 验证结果文件可下载

**Step 4: Docker 构建测试**

```bash
docker compose build
docker compose up -d
```

验证: http://localhost:8080 可访问

**Step 5: 提交**

```bash
git add -A
git commit -m "fix: 集成测试修复"
```

---

### Task 10: 文件清理 + 简单认证

**Files:**
- Create: `backend/app/services/cleanup.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/main.py`

**Step 1: 文件清理服务**

`backend/app/services/cleanup.py`:
```python
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
        await asyncio.sleep(3600)  # 每小时检查一次
```

**Step 2: 简单密码认证**

`backend/app/api/auth.py`:
```python
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
        return {"ok": True}  # 未设密码则跳过认证
    if req.password != AUTH_PASSWORD:
        raise HTTPException(401, "密码错误")
    return {"ok": True}
```

**Step 3: 注册到 main.py 并启动清理任务**

```python
from app.api.auth import router as auth_router
from app.services.cleanup import cleanup_old_files

app.include_router(auth_router)

@app.on_event("startup")
async def startup():
    import asyncio
    asyncio.create_task(cleanup_old_files())
```

**Step 4: 提交**

```bash
git add -A
git commit -m "feat: 文件自动清理 + 简单密码认证"
```

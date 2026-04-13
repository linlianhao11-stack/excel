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
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in (
                "__import__", "exec", "eval", "compile",
            ):
                return f"禁止调用: {func.id}()"
            if isinstance(func, ast.Attribute) and func.attr in (
                "__import__", "system", "popen",
            ):
                return f"禁止调用: .{func.attr}()"

    return None


def _run_script(full_code: str) -> dict:
    """写入临时文件并用子进程执行"""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=str(WORK_DIR)
    ) as f:
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
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[:MAX_OUTPUT_LEN],
            "stderr": result.stderr[:MAX_OUTPUT_LEN],
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"执行超时 ({TIMEOUT}秒)",
        }
    finally:
        Path(script_path).unlink(missing_ok=True)


def _build_header(file_paths: dict[str, str], output_path: str | None = None) -> str:
    header = (
        "import pandas as pd\n"
        "import numpy as np\n"
        "import re\n"
        "from datetime import datetime, timedelta\n\n"
    )
    for var_name, var_path in file_paths.items():
        header += f'{var_name} = r"{var_path}"\n'
    if output_path:
        header += f'OUTPUT_PATH = r"{output_path}"\n'
    header += "\n"
    return header


def execute_code(code: str, file_paths: dict[str, str]) -> dict:
    """执行处理代码并生成结果文件"""
    safety = check_code_safety(code)
    if safety:
        return {
            "success": False, "stdout": "",
            "stderr": f"安全检查失败: {safety}", "output_path": None,
        }

    output_id = uuid.uuid4().hex[:8]
    output_path = str(WORK_DIR / f"result_{output_id}.xlsx")
    full_code = _build_header(file_paths, output_path) + code

    result = _run_script(full_code)
    success = result["returncode"] == 0
    return {
        "success": success,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "output_path": output_path if success and Path(output_path).exists() else None,
    }


def execute_query(code: str, file_paths: dict[str, str]) -> dict:
    """执行只读查询代码，返回 print 输出"""
    safety = check_code_safety(code)
    if safety:
        return {"success": False, "output": f"安全检查失败: {safety}"}

    full_code = _build_header(file_paths) + code
    result = _run_script(full_code)
    output = result["stdout"] if result["returncode"] == 0 else result["stderr"]
    return {"success": result["returncode"] == 0, "output": output}

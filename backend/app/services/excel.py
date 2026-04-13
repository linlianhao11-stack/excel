from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

WORK_DIR = Path(os.environ.get("WORK_DIR", "/data/work"))


def ensure_work_dir() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def save_upload(filename: str, content: bytes) -> dict:
    """保存上传文件，返回文件信息"""
    ensure_work_dir()
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{filename}"
    file_path = WORK_DIR / safe_name
    file_path.write_bytes(content)

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{ext}" in IMAGE_EXTS:
        return {
            "file_id": file_id,
            "filename": filename,
            "path": str(file_path),
            "type": "image",
            "profile": None,
        }

    profile = profile_excel(str(file_path))
    return {
        "file_id": file_id,
        "filename": filename,
        "path": str(file_path),
        "type": "excel",
        "profile": profile,
    }


def profile_excel(path: str) -> dict[str, Any]:
    """分析 Excel/CSV 结构：sheet名、列名、类型、样本、行数"""
    if path.endswith(".csv"):
        df = pd.read_csv(path)
        result = {}
        sample_df = df.head(5)
        result["Sheet1"] = {
            "columns": df.columns.tolist(),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "sample": sample_df.fillna("").astype(str).to_dict("records"),
            "row_count": len(df),
            "col_count": len(df.columns),
        }
        return result

    xl = pd.ExcelFile(path)
    result = {}
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        sample_df = df.head(5)
        result[sheet] = {
            "columns": df.columns.tolist(),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "sample": sample_df.fillna("").astype(str).to_dict("records"),
            "row_count": len(df),
            "col_count": len(df.columns),
        }
    return result


def preview_excel(path: str, max_rows: int = 50) -> dict[str, Any]:
    """返回更多行用于前端表格预览"""
    if path.endswith(".csv"):
        df = pd.read_csv(path)
        preview_df = df.head(max_rows)
        return {
            "Sheet1": {
                "columns": df.columns.tolist(),
                "data": preview_df.fillna("").astype(str).values.tolist(),
                "row_count": len(df),
                "col_count": len(df.columns),
            }
        }

    xl = pd.ExcelFile(path)
    result = {}
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        preview_df = df.head(max_rows)
        result[sheet] = {
            "columns": df.columns.tolist(),
            "data": preview_df.fillna("").astype(str).values.tolist(),
            "row_count": len(df),
            "col_count": len(df.columns),
        }
    return result


def build_context(files: list[dict]) -> str:
    """根据文件 profile 构建给 LLM 的上下文描述"""
    parts = []
    idx = 0
    for f in files:
        if f.get("type") == "image" or not f.get("profile"):
            continue
        idx += 1
        parts.append(f"## 文件 {idx}: {f['filename']} (变量名: INPUT_PATH_{idx})")
        for sheet_name, info in f["profile"].items():
            total_rows = info["row_count"]
            parts.append(f"\n### Sheet: {sheet_name} ({total_rows} 行, {info['col_count']} 列)")
            parts.append(f"列: {info['columns']}")
            parts.append(f"类型: {info['dtypes']}")
            if total_rows <= 200:
                parts.append(f"数据(全量):\n{info['sample']}")
            else:
                parts.append(f"样本(前5行):\n{info['sample']}")
                parts.append("(可用 query 工具探索更多数据)")
    return "\n".join(parts)

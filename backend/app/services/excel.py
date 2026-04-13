from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

WORK_DIR = Path(os.environ.get("WORK_DIR", "/data/work"))


def ensure_work_dir() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)


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
    """分析 Excel/CSV 结构：sheet名、列名、类型、样本、行数"""
    if path.endswith(".csv"):
        df = pd.read_csv(path)
        result = {}
        sample_df = df.head(5)
        result["Sheet1"] = {
            "columns": df.columns.tolist(),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "sample": sample_df.fillna("").to_dict("records"),
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
            "sample": sample_df.fillna("").to_dict("records"),
            "row_count": len(df),
            "col_count": len(df.columns),
        }
    return result


def build_context(files: list[dict]) -> str:
    """根据文件 profile 构建给 LLM 的上下文描述"""
    parts = []
    for i, f in enumerate(files, 1):
        parts.append(f"## 文件 {i}: {f['filename']} (变量名: INPUT_PATH_{i})")
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

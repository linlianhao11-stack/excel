from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import bcrypt

DB_DIR = Path(os.environ.get("DB_DIR", "/data/db"))
DB_PATH = DB_DIR / "excel_agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT,
    tool_calls TEXT,
    output_path TEXT,
    output_display_name TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    profile TEXT
);
"""


def get_db() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript(SCHEMA)

    # 兼容已存在的库：若 is_active 列缺失则补上
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "is_active" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
        conn.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
        conn.commit()

    # 兼容已存在的库：若 messages.output_display_name 列缺失则补上
    msg_cols = {row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
    if "output_display_name" not in msg_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN output_display_name TEXT")
        conn.commit()

    # 创建默认管理员账号（如果不存在）
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()
    if not existing:
        admin_pw = os.environ.get("ADMIN_PASSWORD", "admin123")
        pw_hash = bcrypt.hashpw(admin_pw.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
            ("admin", pw_hash),
        )
        conn.commit()

    # 从环境变量初始化默认设置（如果数据库中没有）
    defaults = {
        "provider": os.environ.get("LLM_PROVIDER", "deepseek"),
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
    }
    for key, value in defaults.items():
        if value:
            existing = conn.execute(
                "SELECT key FROM settings WHERE key = ?", (key,)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?)", (key, value)
                )

    # 注册开关默认开启
    existing = conn.execute(
        "SELECT key FROM settings WHERE key = ?", ("allow_registration",)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            ("allow_registration", "true"),
        )
        conn.commit()
    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
    )
    conn.commit()
    conn.close()

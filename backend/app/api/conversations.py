from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(user: dict = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations "
        "WHERE user_id = ? ORDER BY updated_at DESC",
        (user["user_id"],),
    ).fetchall()
    conn.close()
    return {"conversations": [dict(r) for r in rows]}


@router.post("")
async def create_conversation(user: dict = Depends(get_current_user)):
    conv_id = uuid.uuid4().hex[:16]
    conn = get_db()
    conn.execute(
        "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
        (conv_id, user["user_id"], "新对话"),
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "title": "新对话"}


@router.get("/{conv_id}/messages")
async def get_messages(conv_id: str, user: dict = Depends(get_current_user)):
    conn = get_db()
    # 验证对话属于当前用户
    conv = conn.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user["user_id"]),
    ).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(404, "对话不存在")

    rows = conn.execute(
        "SELECT id, role, content, tool_calls, output_path, output_display_name, error, created_at "
        "FROM messages WHERE conversation_id = ? ORDER BY created_at",
        (conv_id,),
    ).fetchall()

    # 获取对话关联的文件
    files = conn.execute(
        "SELECT file_id, filename, path, profile FROM conversation_files "
        "WHERE conversation_id = ?",
        (conv_id,),
    ).fetchall()
    conn.close()

    messages = []
    for r in rows:
        msg = dict(r)
        if msg["tool_calls"]:
            msg["tool_calls"] = json.loads(msg["tool_calls"])
        messages.append(msg)

    file_list = []
    for f in files:
        fd = dict(f)
        if fd["profile"]:
            fd["profile"] = json.loads(fd["profile"])
        file_list.append(fd)

    return {"messages": messages, "files": file_list}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    conn = get_db()
    conv = conn.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user["user_id"]),
    ).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(404, "对话不存在")
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


def save_message(
    conv_id: str,
    role: str,
    content: str | None = None,
    tool_calls: list | None = None,
    output_path: str | None = None,
    output_display_name: str | None = None,
    error: str | None = None,
) -> None:
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, tool_calls, output_path, output_display_name, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            conv_id,
            role,
            content,
            json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
            output_path,
            output_display_name,
            error,
        ),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (conv_id,),
    )
    conn.commit()
    conn.close()


def update_conversation_title(conv_id: str, title: str) -> None:
    conn = get_db()
    conn.execute(
        "UPDATE conversations SET title = ? WHERE id = ?",
        (title[:30], conv_id),
    )
    conn.commit()
    conn.close()


def save_conversation_files(conv_id: str, files: list[dict]) -> None:
    conn = get_db()
    for f in files:
        conn.execute(
            "INSERT INTO conversation_files (conversation_id, file_id, filename, path, profile) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                conv_id,
                f["file_id"],
                f["filename"],
                f["path"],
                json.dumps(f.get("profile", {}), ensure_ascii=False),
            ),
        )
    conn.commit()
    conn.close()


def update_last_assistant_output(
    conv_id: str, output_path: str, output_display_name: str | None = None
) -> None:
    """审批通过后，将 output_path 写回最近一条 assistant 消息"""
    conn = get_db()
    conn.execute(
        """UPDATE messages SET output_path = ?, output_display_name = ?
           WHERE id = (
               SELECT id FROM messages
               WHERE conversation_id = ? AND role = 'assistant'
               ORDER BY id DESC LIMIT 1
           )""",
        (output_path, output_display_name, conv_id),
    )
    conn.commit()
    conn.close()

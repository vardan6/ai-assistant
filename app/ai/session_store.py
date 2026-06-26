"""Trimmed SQLite session store for CLI/server chat history."""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


class SessionStore:
    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
                """
            )

    def create_session(self, *, title: str = "New chat") -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute("INSERT INTO sessions(id, title) VALUES (?, ?)", (session_id, title))
        return self.get_session_summary(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC, s.created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) AS message_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE s.id = ?
                GROUP BY s.id
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown session '{session_id}'.")
        return dict(row)

    def get_session(self, session_id: str) -> dict[str, Any]:
        summary = self.get_session_summary(session_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, metadata_json, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
        messages = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            messages.append(item)
        summary["messages"] = messages
        return summary

    def append_turn(
        self,
        session_id: str,
        *,
        question: str,
        answer: str,
        metadata: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT title FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                raise KeyError(f"Unknown session '{session_id}'.")
            if row["title"] == "New chat":
                conn.execute(
                    "UPDATE sessions SET title = ? WHERE id = ?",
                    (_title_from_question(question), session_id),
                )
            for role, content, payload in [
                ("user", question, {}),
                ("assistant", answer, metadata),
            ]:
                conn.execute(
                    """
                    INSERT INTO messages(session_id, role, content, metadata_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, role, content, json.dumps(payload, separators=(",", ":"), default=str)),
                )
            conn.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )


def _title_from_question(question: str) -> str:
    clean = " ".join(str(question or "").split())
    if not clean:
        return "New chat"
    return clean[:60]

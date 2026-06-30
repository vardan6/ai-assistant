"""Trimmed SQLite session store for CLI/server chat history."""
from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..config import AppConfig, load_config
from .context_budget import (
    AI_CONTEXT_HISTORY_CHAR_BUDGET,
    AI_CONTEXT_MESSAGE_LIMIT,
    AI_CONTEXT_SINGLE_MESSAGE_CHAR_LIMIT,
    bound_history_window,
    project_history_for_prompt,
    stable_fingerprint,
)


class SessionStore:
    def __init__(
        self,
        db_path: str | Path,
        *,
        config: AppConfig | None = None,
        evidence_fingerprint_resolver: Callable[[], dict[str, Any] | None] | None = None,
    ):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = config
        self._evidence_fingerprint_resolver = evidence_fingerprint_resolver
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
        messages = self._load_messages(session_id)
        summary["messages"] = messages
        return summary

    def load_history_window(
        self,
        session_id: str,
        *,
        message_limit: int = AI_CONTEXT_MESSAGE_LIMIT,
        history_char_budget: int = AI_CONTEXT_HISTORY_CHAR_BUDGET,
        single_message_char_limit: int = AI_CONTEXT_SINGLE_MESSAGE_CHAR_LIMIT,
    ) -> list[dict[str, Any]]:
        return bound_history_window(
            self._load_messages(session_id),
            message_limit=message_limit,
            history_char_budget=history_char_budget,
            single_message_char_limit=single_message_char_limit,
        )

    def load_prompt_history(
        self,
        session_id: str,
        *,
        message_limit: int = AI_CONTEXT_MESSAGE_LIMIT,
        history_char_budget: int = AI_CONTEXT_HISTORY_CHAR_BUDGET,
        single_message_char_limit: int = AI_CONTEXT_SINGLE_MESSAGE_CHAR_LIMIT,
    ) -> list[dict[str, str]]:
        return project_history_for_prompt(
            self.load_history_window(
                session_id,
                message_limit=message_limit,
                history_char_budget=history_char_budget,
                single_message_char_limit=single_message_char_limit,
            )
        )

    def update_session_title(self, session_id: str, *, title: str) -> None:
        next_title = " ".join(str(title or "").split()) or "New chat"
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (next_title, session_id),
            )
            if result.rowcount == 0:
                raise KeyError(f"Unknown session '{session_id}'.")

    def delete_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            result = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            if result.rowcount == 0:
                raise KeyError(f"Unknown session '{session_id}'.")

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
            assistant_metadata = self._assistant_metadata_with_fingerprint(metadata)
            for role, content, payload in [
                ("user", question, {}),
                ("assistant", answer, assistant_metadata),
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

    def _load_messages(self, session_id: str) -> list[dict[str, Any]]:
        self.get_session_summary(session_id)
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
        return messages

    def _assistant_metadata_with_fingerprint(self, metadata: dict[str, Any]) -> dict[str, Any]:
        payload = dict(metadata)
        snapshot = self._resolve_evidence_fingerprint_snapshot()
        if not snapshot:
            return payload
        payload["evidence_fingerprint"] = {
            **snapshot,
            "sha256": stable_fingerprint(snapshot),
        }
        return payload

    def _resolve_evidence_fingerprint_snapshot(self) -> dict[str, Any] | None:
        if self._evidence_fingerprint_resolver is not None:
            snapshot = self._evidence_fingerprint_resolver()
            return snapshot if isinstance(snapshot, dict) and snapshot else None
        config = self._config or self._load_matching_default_config()
        if config is None:
            return None
        return _build_evidence_fingerprint_snapshot(config)

    def _load_matching_default_config(self) -> AppConfig | None:
        config = load_config()
        try:
            if config.ai_sessions_db_path.resolve() != self._db_path.resolve():
                return None
        except OSError:
            return None
        return config


def _title_from_question(question: str) -> str:
    clean = " ".join(str(question or "").split())
    if not clean:
        return "New chat"
    return clean[:60]


def _build_evidence_fingerprint_snapshot(config: AppConfig) -> dict[str, Any]:
    return {
        "dataset": {
            "csv_dir": config.csv_dir_setting,
            "csv_files": config.csv_files,
            "resolved_csv_paths": {
                table_name: str(path)
                for table_name, path in sorted(config.resolved_csv_paths().items())
            },
        },
        "config": {
            "use_reference_now_anchor": config.use_reference_now_anchor,
            "default_gating_mode": config.default_gating_mode,
        },
    }

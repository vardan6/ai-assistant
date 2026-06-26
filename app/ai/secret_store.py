"""SQLite-backed secret storage keyed by secret_ref."""
from __future__ import annotations

import sqlite3
from pathlib import Path


class SecretStore:
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
                CREATE TABLE IF NOT EXISTS secrets (
                    secret_ref TEXT PRIMARY KEY,
                    secret_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self, secret_ref: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT secret_value FROM secrets WHERE secret_ref = ?",
                (secret_ref,),
            ).fetchone()
        return str(row["secret_value"]) if row else ""

    def set(self, secret_ref: str, secret_value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO secrets(secret_ref, secret_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(secret_ref) DO UPDATE SET
                    secret_value = excluded.secret_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (secret_ref, secret_value),
            )

    def delete(self, secret_ref: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM secrets WHERE secret_ref = ?", (secret_ref,))

    def has(self, secret_ref: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM secrets WHERE secret_ref = ?",
                (secret_ref,),
            ).fetchone()
        return row is not None

"""Helpers for loading bounded conversation history into prompt context."""
from __future__ import annotations

import hashlib
import json
from typing import Any

AI_CONTEXT_MESSAGE_LIMIT = 40
AI_CONTEXT_HISTORY_CHAR_BUDGET = 16000
AI_CONTEXT_SINGLE_MESSAGE_CHAR_LIMIT = 4000
AI_CONTEXT_TRUNCATION_MARKER = "[earlier message truncated for context budget]"


def truncate_message_content(content: str, *, char_limit: int = AI_CONTEXT_SINGLE_MESSAGE_CHAR_LIMIT) -> str:
    text = str(content or "")
    if char_limit <= 0 or len(text) <= char_limit:
        return text
    marker = AI_CONTEXT_TRUNCATION_MARKER
    if char_limit <= len(marker):
        return marker[:char_limit]
    tail_limit = char_limit - len(marker) - 1
    return f"{marker}\n{text[-tail_limit:]}"


def bound_history_window(
    messages: list[dict[str, Any]],
    *,
    message_limit: int = AI_CONTEXT_MESSAGE_LIMIT,
    history_char_budget: int = AI_CONTEXT_HISTORY_CHAR_BUDGET,
    single_message_char_limit: int = AI_CONTEXT_SINGLE_MESSAGE_CHAR_LIMIT,
) -> list[dict[str, Any]]:
    """Return a chronological recency window with capped message content."""
    if not messages:
        return []

    recent = list(messages[-max(message_limit, 1) :])
    kept_newest_first: list[dict[str, Any]] = []
    total_chars = 0

    for index, message in enumerate(reversed(recent)):
        bounded = dict(message)
        bounded["content"] = truncate_message_content(
            str(message.get("content", "")),
            char_limit=single_message_char_limit,
        )
        content_len = len(bounded["content"])
        is_latest = index == 0
        if not is_latest and total_chars + content_len > history_char_budget:
            continue
        kept_newest_first.append(bounded)
        total_chars += content_len

    kept_newest_first.reverse()
    return kept_newest_first


def project_history_for_prompt(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Strip stored metadata so prompt history contains prose only."""
    projected: list[dict[str, str]] = []
    for message in messages:
        projected.append(
            {
                "role": str(message.get("role", "")),
                "content": str(message.get("content", "")),
            }
        )
    return projected


def stable_fingerprint(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

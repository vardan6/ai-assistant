from __future__ import annotations

import json

from app.ai.context_budget import AI_CONTEXT_TRUNCATION_MARKER
from app.ai.session_store import SessionStore
from app.config import AppConfig, DEFAULT_SETTINGS


def _seed_turn(
    store: SessionStore,
    session_id: str,
    *,
    question: str,
    answer: str,
    metadata: dict | None = None,
) -> None:
    store.append_turn(session_id, question=question, answer=answer, metadata=metadata or {})


def test_load_history_window_applies_message_limit(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session_id = store.create_session(title="Budget test")["id"]

    for index in range(3):
        _seed_turn(
            store,
            session_id,
            question=f"user-{index}",
            answer=f"assistant-{index}",
        )

    messages = store.load_history_window(session_id, message_limit=4, history_char_budget=10_000)
    assert [message["content"] for message in messages] == [
        "user-1",
        "assistant-1",
        "user-2",
        "assistant-2",
    ]


def test_load_history_window_keeps_latest_message_when_budget_drops_older_ones(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session_id = store.create_session(title="Budget test")["id"]
    char_limit = len(AI_CONTEXT_TRUNCATION_MARKER) + 10

    _seed_turn(
        store,
        session_id,
        question="old-user",
        answer="old-assistant",
    )
    _seed_turn(
        store,
        session_id,
        question="latest-user",
        answer="x" * (char_limit + 20),
    )

    messages = store.load_history_window(
        session_id,
        history_char_budget=20,
        single_message_char_limit=char_limit,
    )

    assert len(messages) == 1
    assert messages[0]["role"] == "assistant"
    assert messages[0]["content"].startswith(AI_CONTEXT_TRUNCATION_MARKER)


def test_load_history_window_truncates_oversized_messages_with_marker(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session_id = store.create_session(title="Budget test")["id"]
    char_limit = len(AI_CONTEXT_TRUNCATION_MARKER) + 12

    _seed_turn(
        store,
        session_id,
        question="question",
        answer="prefix-" + ("a" * (char_limit + 20)),
        metadata={"tool_rows": [{"raw": True}]},
    )

    messages = store.load_history_window(
        session_id,
        history_char_budget=200,
        single_message_char_limit=char_limit,
    )

    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[-1]["content"].startswith(AI_CONTEXT_TRUNCATION_MARKER)
    assert messages[-1]["content"].endswith("a" * (char_limit - len(AI_CONTEXT_TRUNCATION_MARKER) - 1))


def test_load_prompt_history_projects_only_role_and_content(tmp_path):
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session_id = store.create_session(title="Prompt projection")["id"]

    _seed_turn(
        store,
        session_id,
        question="Which inverters are affected?",
        answer="Two inverters match the filter.",
        metadata={
            "tool_rows": [{"inverter_id": "inv_4135001_09", "raw": True}],
            "trace_events": [{"kind": "tool_finished"}],
            "stop_reason": "final_answer",
        },
    )

    prompt_history = store.load_prompt_history(session_id, history_char_budget=10_000)

    assert prompt_history == [
        {"role": "user", "content": "Which inverters are affected?"},
        {"role": "assistant", "content": "Two inverters match the filter."},
    ]
    assert all(set(message.keys()) == {"role", "content"} for message in prompt_history)
    serialized = str(prompt_history)
    assert "tool_rows" not in serialized
    assert "trace_events" not in serialized
    assert "inv_4135001_09" not in serialized


def test_append_turn_persists_full_evidence_with_fingerprint(tmp_path):
    config = AppConfig(
        raw=json.loads(json.dumps(DEFAULT_SETTINGS)),
        settings_path=tmp_path / "common.local.json",
    )
    store = SessionStore(tmp_path / "sessions.sqlite3", config=config)
    session_id = store.create_session(title="Evidence fingerprint")["id"]

    metadata = {
        "tool_calls": [{"name": "anomalies", "result": {"matched": 2}}],
        "trace_events": [{"kind": "tool_finished"}],
        "stop_reason": "final_answer",
    }
    _seed_turn(
        store,
        session_id,
        question="Which anomalies match?",
        answer="Two anomalies match.",
        metadata=metadata,
    )

    session = store.get_session(session_id)
    assistant = session["messages"][-1]
    stored_metadata = assistant["metadata"]

    assert stored_metadata["tool_calls"] == metadata["tool_calls"]
    assert stored_metadata["trace_events"] == metadata["trace_events"]
    assert stored_metadata["stop_reason"] == "final_answer"
    assert stored_metadata["evidence_fingerprint"]["dataset"]["csv_dir"] == "input/tables-extracted"
    assert stored_metadata["evidence_fingerprint"]["config"]["use_reference_now_anchor"] is True
    assert len(stored_metadata["evidence_fingerprint"]["sha256"]) == 64

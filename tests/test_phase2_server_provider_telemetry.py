from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.ai import AgentResult, TelemetrySummary, ToolCallRecord, TraceEvent, UsageSnapshot
from app.ai.secret_store import SecretStore
from app.ai.session_store import SessionStore
from app.config import AppConfig, DEFAULT_SETTINGS, load_config
from app.pipeline import Pipeline, PipelineAnswer
from app.provider_config import update_provider_settings
from app.server import create_app


def test_secret_store_and_provider_settings_persist(tmp_path):
    settings_path = tmp_path / "common.local.json"
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=settings_path)

    updated = update_provider_settings(
        config,
        llm_providers=[
            {
                "id": "ollama-local",
                "display_name": "Ollama",
                "provider_type": "ollama",
                "model_id": "qwen2.5:latest",
                "auth_mode": "none",
                "secret_ref": "",
                "base_url": "http://localhost:11434",
                "enabled": True,
            }
        ],
        model_routing={
            "intent": {"primary_provider_id": "ollama-local", "fallback_provider_ids": []},
            "synthesis": {"primary_provider_id": "ollama-local", "fallback_provider_ids": []},
        },
    )

    reloaded = load_config(updated.settings_path)
    assert reloaded.llm_providers[0]["id"] == "ollama-local"
    assert reloaded.model_routing["intent"]["primary_provider_id"] == "ollama-local"

    secrets = SecretStore(tmp_path / "secrets.sqlite3")
    assert secrets.has("OPENAI_API_KEY") is False
    secrets.set("OPENAI_API_KEY", "secret-value")
    assert secrets.has("OPENAI_API_KEY") is True
    assert secrets.get("OPENAI_API_KEY") == "secret-value"
    secrets.delete("OPENAI_API_KEY")
    assert secrets.get("OPENAI_API_KEY") == ""


def test_pipeline_returns_telemetry_and_trace(monkeypatch):
    pipeline = Pipeline(load_config())

    class StubIntentService:
        def parse(self, user_prompt, *, model, context_summary=""):  # noqa: ARG002
            return {
                "intent": {
                    "types": ["A"],
                    "entities": {"plants": [], "inverters": [], "alerts": [], "anomalies": [], "maintenance": []},
                    "time_range": "today",
                    "metric": "status",
                    "out_of_scope": False,
                    "confidence": 0.9,
                    "summary": "Plant status",
                },
                "parse_errors": [],
                "provider_name": "fake-intent-model",
                "latency_ms": 5,
                "fast_path": "",
                "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            }

    def fake_resolve_provider(config, *, purpose, provider_id="", secret_resolver=None):  # noqa: ARG001
        return SimpleNamespace(model=SimpleNamespace(model_name=f"{purpose}-model"))

    def fake_run_agent_loop(model, *, system_prompt, user_prompt, registry, context, tool_names, event_handler=None):  # noqa: ARG001
        if event_handler is not None:
            event_handler(TraceEvent(kind="tool_started", timestamp="2026-06-27T00:00:00+00:00", message="Calling tool", tool_name="plants"))
            event_handler(TraceEvent(kind="tool_finished", timestamp="2026-06-27T00:00:01+00:00", message="Tool finished", tool_name="plants", latency_ms=12, ok=True))
        return AgentResult(
            answer="Tamil Nadu PV Plant is offline.",
            tool_calls=[ToolCallRecord(name="plants", args={"status": "offline"}, result={"ok": True}, iteration=1, latency_ms=12)],
            iterations=1,
            stop_reason="final_answer",
            trace_events=[],
            usage=UsageSnapshot(input_tokens=20, output_tokens=10, total_tokens=30),
            elapsed_ms=15,
            model_name="synthesis-model",
        )

    pipeline._intent_service = StubIntentService()
    monkeypatch.setattr("app.pipeline.resolve_provider", fake_resolve_provider)
    monkeypatch.setattr("app.pipeline.run_agent_loop", fake_run_agent_loop)

    result = pipeline.answer("Which plants are offline?")
    assert result.answer == "Tamil Nadu PV Plant is offline."
    assert result.telemetry.intent_usage.total_tokens == 18
    assert result.telemetry.synthesis_usage.total_tokens == 30
    assert result.telemetry.total_usage.total_tokens == 48
    assert [event.kind for event in result.trace_events] == [
        "intent_started",
        "intent_finished",
        "synthesis_started",
        "tool_started",
        "tool_finished",
    ]


def test_server_streams_chat_and_persists_session(tmp_path):
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    session_store = SessionStore(tmp_path / "sessions.sqlite3")
    secret_store = SecretStore(tmp_path / "secrets.sqlite3")

    class FakePipeline:
        dataset_today = datetime.fromisoformat("2026-06-22T23:50:00")

        def answer(self, question, *, provider_id="", gating_mode="gated", event_handler=None):  # noqa: ARG002
            if event_handler is not None:
                event_handler(TraceEvent(kind="tool_started", timestamp="2026-06-27T00:00:00+00:00", message="Calling tool 'plants'", tool_name="plants"))
                event_handler(TraceEvent(kind="tool_finished", timestamp="2026-06-27T00:00:01+00:00", message="Tool 'plants' completed", tool_name="plants", latency_ms=9, ok=True))
            return PipelineAnswer(
                answer="One plant is offline.",
                intent={
                    "types": ["A"],
                    "entities": {"plants": [], "inverters": [], "alerts": [], "anomalies": [], "maintenance": []},
                    "time_range": "today",
                    "metric": "status",
                    "out_of_scope": False,
                    "confidence": 0.95,
                    "summary": "Offline plants",
                },
                intent_meta={"provider_name": "fake", "latency_ms": 4, "parse_errors": [], "fast_path": ""},
                gating_mode=gating_mode,
                bound_tools=["plants"],
                iterations=1,
                trace_events=[],
                telemetry=TelemetrySummary(
                    started_at="2026-06-27T00:00:00+00:00",
                    finished_at="2026-06-27T00:00:01+00:00",
                    elapsed_ms=1000,
                    intent_model="intent-model",
                    synthesis_model="synth-model",
                    intent_usage=UsageSnapshot(input_tokens=5, output_tokens=3, total_tokens=8),
                    synthesis_usage=UsageSnapshot(input_tokens=10, output_tokens=4, total_tokens=14),
                ),
            )

    client = TestClient(create_app(config=config, pipeline=FakePipeline(), session_store=session_store, secret_store=secret_store))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["dataset_today"] == "2026-06-22T23:50:00"

    created = client.post("/api/sessions", json={"title": "CLI chat"})
    session_id = created.json()["id"]

    streamed = client.post(
        "/api/chat/stream",
        json={"question": "Which plants are offline?", "session_id": session_id},
    )
    assert streamed.status_code == 200
    lines = [json.loads(line) for line in streamed.text.splitlines() if line.strip()]
    assert [line["type"] for line in lines] == ["trace", "trace", "final"]
    assert lines[-1]["response"]["answer"] == "One plant is offline."

    session = client.get(f"/api/sessions/{session_id}")
    assert session.status_code == 200
    body = session.json()
    assert body["title"] == "CLI chat"
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]


def test_server_serves_web_ui_and_assets(tmp_path):
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    client = TestClient(create_app(config=config))

    index = client.get("/")
    assert index.status_code == 200
    assert 'id="provider-select"' in index.text
    assert 'id="providers-form"' in index.text
    assert 'src="/assets/app.js"' in index.text

    app_js = client.get("/assets/app.js")
    assert app_js.status_code == 200
    assert "function sendMessage()" in app_js.text

    styles = client.get("/assets/styles.css")
    assert styles.status_code == 200
    assert ".shell" in styles.text


def test_ui_settings_round_trip(tmp_path):
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    client = TestClient(create_app(config=config))

    original = client.get("/api/settings/ui")
    assert original.status_code == 200
    assert original.json() == {
        "default_gating_mode": "gated",
        "verbose_trace": True,
    }

    updated = client.put(
        "/api/settings/ui",
        json={"default_gating_mode": "bind_all", "verbose_trace": False},
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "default_gating_mode": "bind_all",
        "verbose_trace": False,
    }

    reloaded = client.get("/api/settings/ui")
    assert reloaded.status_code == 200
    assert reloaded.json() == {
        "default_gating_mode": "bind_all",
        "verbose_trace": False,
    }

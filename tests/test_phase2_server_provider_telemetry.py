from __future__ import annotations

import base64
import io
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.ai import AgentResult, TelemetrySummary, ToolCallRecord, TraceEvent, UsageSnapshot
from app.ai.secret_store import SecretStore
from app.ai.session_store import SessionStore
from app.config import AppConfig, DEFAULT_SETTINGS, ROOT_DIR, load_config
from app.pipeline import Pipeline, PipelineAnswer
from app.provider_config import export_config_payload, import_config_payload, update_provider_settings
from app.server import create_app


def _copy_dataset(tmp_path: Path, name: str = "dataset") -> Path:
    target = tmp_path / name
    shutil.copytree(ROOT_DIR / "input" / "tables-extracted", target)
    return target


def _write_malformed_plants_csv(path: Path) -> None:
    path.write_text("plant_id\nP1\nP2\nP3\n", encoding="utf-8")


def _dataset_zip_base64(default_dir: Path) -> str:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        for table_name in (
            "plants",
            "inverters",
            "generation_readings",
            "weather_readings",
            "alerts",
            "anomalies",
            "maintenance",
        ):
            archive.write(default_dir / f"{table_name}.csv", arcname=f"nested/{table_name.upper()}.csv")
        archive.writestr("nested/ignored.txt", "ignored")
    archive_bytes.seek(0)
    return base64.b64encode(archive_bytes.getvalue()).decode("ascii")


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


def test_config_export_import_round_trip(tmp_path):
    settings_path = tmp_path / "common.local.json"
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=settings_path)

    exported = export_config_payload(config)
    assert "appearance" in exported
    assert exported["llm_providers"][0]["secret_ref"] == "OPENAI_API_KEY"

    exported["appearance"]["theme_mode"] = "system"
    exported["appearance"]["light_theme"] = "cool_light"
    exported["ui"]["verbose_trace"] = False
    exported["llm_providers"][0]["model_id"] = "gpt-4.1-mini"
    exported["data"]["csv_files"] = {"plants": "input/custom/plants.csv"}
    imported = import_config_payload(config, payload=exported)

    reloaded = load_config(imported.settings_path)
    assert reloaded.appearance["theme_mode"] == "system"
    assert reloaded.appearance["light_theme"] == "cool_light"
    assert reloaded.verbose_trace is False
    assert reloaded.llm_providers[0]["model_id"] == "gpt-4.1-mini"
    assert reloaded.csv_files == {"plants": "input/custom/plants.csv"}
    assert reloaded.resolved_csv_paths()["plants"].as_posix().endswith("input/custom/plants.csv")


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
    assert result.stop_reason == "final_answer"
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
        reference_now = datetime.fromisoformat("2026-06-22T23:50:00")

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
                stop_reason="final_answer",
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
    assert health.json()["reference_now"] == "2026-06-22T23:50:00"
    assert health.json()["use_reference_now_anchor"] is True

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
    assert lines[-1]["response"]["stop_reason"] == "final_answer"

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
    assert 'id="chat-provider-summary"' in index.text
    assert 'id="providers-form"' in index.text
    assert 'id="provider-display-name"' in index.text
    assert 'id="providers-registry-pill"' in index.text
    assert 'id="appearance-theme-mode"' in index.text
    assert 'id="dataset-settings-form"' in index.text
    assert 'id="dataset-import-zip-button"' in index.text
    assert 'id="settings-use-reference-now-anchor"' in index.text
    assert 'data-dataset-upload-table="plants"' in index.text
    assert 'data-subtab="dataset"' in index.text
    assert 'value="sandstone_light"' in index.text
    assert 'data-prompt="Which plants are offline today?"' in index.text
    assert 'src="/assets/app.js"' in index.text

    app_js = client.get("/assets/app.js")
    assert app_js.status_code == 200
    assert "function sendMessage()" in app_js.text
    assert "function executeCommand(commandText)" in app_js.text
    assert "function renderCommandMenu()" in app_js.text
    assert "function updateChatControlSummaries()" in app_js.text
    assert "function renderProviderRegistry()" in app_js.text
    assert "function renderDatasetSettings()" in app_js.text
    assert "function uploadDatasetTable(tableName)" in app_js.text
    assert "function importDatasetZip()" in app_js.text

    styles = client.get("/assets/styles.css")
    assert styles.status_code == 200
    assert ".appbar" in styles.text
    assert ".chat-workspace" in styles.text
    assert ".appearance-reference-card" in styles.text
    assert ".provider-registry-table" in styles.text
    assert ".command-menu" in styles.text
    assert ".dataset-settings-card" in styles.text


def test_dataset_settings_save_reload_reset_are_atomic(tmp_path):
    alt_dir = _copy_dataset(tmp_path, "alt-dataset")
    custom_plants = tmp_path / "plants-custom.csv"
    shutil.copy2(alt_dir / "plants.csv", custom_plants)

    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    session_store = SessionStore(tmp_path / "sessions.sqlite3")
    secret_store = SecretStore(tmp_path / "secrets.sqlite3")
    client = TestClient(create_app(config=config, session_store=session_store, secret_store=secret_store))

    initial = client.get("/api/settings/dataset")
    assert initial.status_code == 200
    assert initial.json()["config"]["csv_dir"] == "input/tables-extracted"

    saved = client.put(
        "/api/settings/dataset",
        json={
            "csv_dir": str(alt_dir),
            "csv_files": {"plants": str(custom_plants)},
        },
    )
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["config"]["csv_dir"] == str(alt_dir)
    plants_entry = next(item for item in payload["status"]["tables"] if item["name"] == "plants")
    assert plants_entry["override_path"] == str(custom_plants)
    assert plants_entry["resolved_path"] == str(custom_plants)

    reloaded = load_config(config.settings_path)
    assert reloaded.csv_dir == alt_dir
    assert reloaded.csv_files == {"plants": str(custom_plants)}

    bad_dir = tmp_path / "missing-dataset"
    bad_dir.mkdir()
    failed = client.put(
        "/api/settings/dataset",
        json={
            "csv_dir": str(bad_dir),
            "csv_files": {},
        },
    )
    assert failed.status_code == 400
    assert "Dataset validation failed" in failed.json()["detail"]

    unchanged = load_config(config.settings_path)
    assert unchanged.csv_dir == alt_dir
    assert unchanged.csv_files == {"plants": str(custom_plants)}

    malformed_plants = tmp_path / "plants-malformed.csv"
    _write_malformed_plants_csv(malformed_plants)
    schema_failed = client.put(
        "/api/settings/dataset",
        json={
            "csv_dir": str(alt_dir),
            "csv_files": {"plants": str(malformed_plants)},
        },
    )
    assert schema_failed.status_code == 400
    assert "Dataset schema invalid for table 'plants'" in schema_failed.json()["detail"]

    unchanged = load_config(config.settings_path)
    assert unchanged.csv_dir == alt_dir
    assert unchanged.csv_files == {"plants": str(custom_plants)}

    _write_malformed_plants_csv(custom_plants)
    reload_failed = client.post("/api/settings/dataset/reload")
    assert reload_failed.status_code == 400
    assert "Dataset schema invalid for table 'plants'" in reload_failed.json()["detail"]

    unchanged = load_config(config.settings_path)
    assert unchanged.csv_dir == alt_dir
    assert unchanged.csv_files == {"plants": str(custom_plants)}

    reload_response = client.post("/api/settings/dataset/reload")
    assert reload_response.status_code == 400

    shutil.copy2(alt_dir / "plants.csv", custom_plants)
    reload_response = client.post("/api/settings/dataset/reload")
    assert reload_response.status_code == 200
    assert reload_response.json()["config"]["csv_dir"] == str(alt_dir)

    reset = client.post("/api/settings/dataset/reset")
    assert reset.status_code == 200
    assert reset.json()["config"]["csv_dir"] == "input/tables-extracted"
    assert reset.json()["config"]["csv_files"] == {
        "plants": "",
        "inverters": "",
        "generation_readings": "",
        "weather_readings": "",
        "alerts": "",
        "anomalies": "",
        "maintenance": "",
    }


def test_dataset_upload_and_zip_import_are_atomic(tmp_path):
    default_dir = ROOT_DIR / "input" / "tables-extracted"
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    session_store = SessionStore(tmp_path / "sessions.sqlite3")
    secret_store = SecretStore(tmp_path / "secrets.sqlite3")
    client = TestClient(create_app(config=config, session_store=session_store, secret_store=secret_store))

    custom_plants = tmp_path / "plants-upload.csv"
    shutil.copy2(default_dir / "plants.csv", custom_plants)
    uploaded = client.post(
        "/api/settings/dataset/upload/plants",
        json={
            "filename": "plants.csv",
            "content": custom_plants.read_text(encoding="utf-8"),
        },
    )
    assert uploaded.status_code == 200
    uploaded_payload = uploaded.json()
    plants_entry = next(item for item in uploaded_payload["status"]["tables"] if item["name"] == "plants")
    assert plants_entry["source"] == "override"
    assert plants_entry["override_path"].startswith("data/managed_datasets/overrides/plants-")
    assert Path(plants_entry["resolved_path"]).exists()

    reloaded = load_config(config.settings_path)
    assert reloaded.csv_files["plants"].startswith("data/managed_datasets/overrides/plants-")

    malformed_upload = client.post(
        "/api/settings/dataset/upload/plants",
        json={
            "filename": "plants.csv",
            "content": "plant_id\nP1\nP2\n",
        },
    )
    assert malformed_upload.status_code == 400
    assert "Dataset schema invalid for table 'plants'" in malformed_upload.json()["detail"]

    unchanged = load_config(config.settings_path)
    assert unchanged.csv_files["plants"].startswith("data/managed_datasets/overrides/plants-")

    imported = client.post(
        "/api/settings/dataset/import-zip",
        json={
            "filename": "dataset.zip",
            "content_base64": _dataset_zip_base64(default_dir),
        },
    )
    assert imported.status_code == 200
    imported_payload = imported.json()
    assert imported_payload["config"]["csv_dir"].startswith("data/managed_datasets/imports/dataset-")
    assert imported_payload["config"]["csv_files"] == {
        "plants": "",
        "inverters": "",
        "generation_readings": "",
        "weather_readings": "",
        "alerts": "",
        "anomalies": "",
        "maintenance": "",
    }

    imported_config = load_config(config.settings_path)
    assert imported_config.csv_dir_setting.startswith("data/managed_datasets/imports/dataset-")
    assert imported_config.csv_files == {}

    bad_archive = io.BytesIO()
    with zipfile.ZipFile(bad_archive, "w") as archive:
        for table_name in ("plants", "inverters", "generation_readings", "weather_readings", "alerts", "anomalies"):
            archive.write(default_dir / f"{table_name}.csv", arcname=f"{table_name}.csv")
    bad_archive.seek(0)

    failed = client.post(
        "/api/settings/dataset/import-zip",
        json={
            "filename": "broken.zip",
            "content_base64": base64.b64encode(bad_archive.getvalue()).decode("ascii"),
        },
    )
    assert failed.status_code == 400
    assert "missing required CSVs" in failed.json()["detail"]

    malformed_archive = io.BytesIO()
    with zipfile.ZipFile(malformed_archive, "w") as archive:
        for table_name in (
            "inverters",
            "generation_readings",
            "weather_readings",
            "alerts",
            "anomalies",
            "maintenance",
        ):
            archive.write(default_dir / f"{table_name}.csv", arcname=f"{table_name}.csv")
        archive.writestr("plants.csv", "plant_id\nP1\nP2\n")
    malformed_archive.seek(0)

    malformed_import = client.post(
        "/api/settings/dataset/import-zip",
        json={
            "filename": "broken-schema.zip",
            "content_base64": base64.b64encode(malformed_archive.getvalue()).decode("ascii"),
        },
    )
    assert malformed_import.status_code == 400
    assert "Dataset schema invalid for table 'plants'" in malformed_import.json()["detail"]

    unchanged = load_config(config.settings_path)
    assert unchanged.csv_dir_setting == imported_config.csv_dir_setting
    assert unchanged.csv_files == {}


def test_managed_dataset_artifacts_are_pruned_after_successful_activation(tmp_path):
    default_dir = ROOT_DIR / "input" / "tables-extracted"
    alt_dir = _copy_dataset(tmp_path, "alt-dataset")
    user_override = tmp_path / "plants-user.csv"
    shutil.copy2(default_dir / "plants.csv", user_override)

    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    session_store = SessionStore(tmp_path / "sessions.sqlite3")
    secret_store = SecretStore(tmp_path / "secrets.sqlite3")
    client = TestClient(create_app(config=config, session_store=session_store, secret_store=secret_store))

    first_upload = client.post(
        "/api/settings/dataset/upload/plants",
        json={
            "filename": "plants.csv",
            "content": (default_dir / "plants.csv").read_text(encoding="utf-8"),
        },
    )
    assert first_upload.status_code == 200
    first_override = ROOT_DIR / next(
        item["override_path"]
        for item in first_upload.json()["status"]["tables"]
        if item["name"] == "plants"
    )
    assert first_override.exists()

    second_upload = client.post(
        "/api/settings/dataset/upload/plants",
        json={
            "filename": "plants.csv",
            "content": (default_dir / "plants.csv").read_text(encoding="utf-8"),
        },
    )
    assert second_upload.status_code == 200
    second_override = ROOT_DIR / next(
        item["override_path"]
        for item in second_upload.json()["status"]["tables"]
        if item["name"] == "plants"
    )
    assert second_override.exists()
    assert first_override.exists() is False

    imported = client.post(
        "/api/settings/dataset/import-zip",
        json={
            "filename": "dataset.zip",
            "content_base64": _dataset_zip_base64(default_dir),
        },
    )
    assert imported.status_code == 200
    managed_import_dir = ROOT_DIR / imported.json()["config"]["csv_dir"]
    assert managed_import_dir.exists()
    assert second_override.exists() is False

    switched = client.put(
        "/api/settings/dataset",
        json={
            "csv_dir": str(alt_dir),
            "csv_files": {"plants": str(user_override)},
        },
    )
    assert switched.status_code == 200
    assert managed_import_dir.exists() is False
    assert user_override.exists()
    assert alt_dir.exists()


def test_server_lists_and_executes_chat_commands(tmp_path):
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    session_store = SessionStore(tmp_path / "sessions.sqlite3")
    secret_store = SecretStore(tmp_path / "secrets.sqlite3")
    client = TestClient(create_app(config=config, session_store=session_store, secret_store=secret_store))

    commands = client.get("/api/chat/commands")
    assert commands.status_code == 200
    command_names = [item["name"] for item in commands.json()["commands"]]
    assert command_names == ["context", "data", "tools"]

    created = client.post("/api/sessions", json={"title": "Commands"})
    session_id = created.json()["id"]

    executed = client.post(
        "/api/chat/commands/execute",
        json={"command": "/tools", "session_id": session_id},
    )
    assert executed.status_code == 200
    payload = executed.json()
    assert payload["command"]["name"] == "tools"
    assert payload["metadata"]["kind"] == "slash_command"
    assert payload["metadata"]["tool_count"] >= 1
    assert "Available tools" in payload["answer"]
    assert "`plants`" in payload["answer"]

    session = client.get(f"/api/sessions/{session_id}")
    assert session.status_code == 200
    body = session.json()
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["content"] == "/tools"
    assert body["messages"][1]["metadata"]["command"]["name"] == "tools"


def test_appearance_settings_round_trip(tmp_path):
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    client = TestClient(create_app(config=config))

    original = client.get("/api/settings/appearance")
    assert original.status_code == 200
    assert original.json() == {
        "theme_mode": "light",
        "light_theme": "quiet_light",
        "dark_theme": "vscode_dark",
    }

    updated = client.put(
        "/api/settings/appearance",
        json={"theme_mode": "system", "light_theme": "sandstone_light", "dark_theme": "midnight_dark"},
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "theme_mode": "system",
        "light_theme": "sandstone_light",
        "dark_theme": "midnight_dark",
    }

    reloaded = client.get("/api/settings/appearance")
    assert reloaded.status_code == 200
    assert reloaded.json()["light_theme"] == "sandstone_light"

    rejected = client.put(
        "/api/settings/appearance",
        json={"theme_mode": "nope", "light_theme": "quiet_light", "dark_theme": "vscode_dark"},
    )
    assert rejected.status_code == 400


def test_ui_settings_round_trip(tmp_path):
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    client = TestClient(create_app(config=config))

    original = client.get("/api/settings/ui")
    assert original.status_code == 200
    assert original.json() == {
        "default_gating_mode": "gated",
        "verbose_trace": True,
        "use_reference_now_anchor": True,
    }

    updated = client.put(
        "/api/settings/ui",
        json={"default_gating_mode": "bind_all", "verbose_trace": False, "use_reference_now_anchor": False},
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "default_gating_mode": "bind_all",
        "verbose_trace": False,
        "use_reference_now_anchor": False,
    }

    reloaded = client.get("/api/settings/ui")
    assert reloaded.status_code == 200
    assert reloaded.json() == {
        "default_gating_mode": "bind_all",
        "verbose_trace": False,
        "use_reference_now_anchor": False,
    }


def test_server_config_io_round_trip_and_validation(tmp_path):
    config = AppConfig(raw=json.loads(json.dumps(DEFAULT_SETTINGS)), settings_path=tmp_path / "common.local.json")
    client = TestClient(create_app(config=config))

    exported = client.get("/api/settings/config")
    assert exported.status_code == 200
    payload = exported.json()["config"]
    assert payload["appearance"]["light_theme"] == "quiet_light"

    payload["appearance"]["light_theme"] = "vscode_light"
    payload["ui"]["default_gating_mode"] = "bind_all"
    payload["llm_providers"][1]["base_url"] = "http://127.0.0.1:11434"

    imported = client.put("/api/settings/config", json={"config": payload})
    assert imported.status_code == 200
    body = imported.json()
    assert body["appearance"]["light_theme"] == "vscode_light"
    assert body["ui"]["default_gating_mode"] == "bind_all"
    assert body["llm_providers"][1]["base_url"] == "http://127.0.0.1:11434"

    malformed_dataset_dir = _copy_dataset(tmp_path, "bad-config-dataset")
    malformed_plants = tmp_path / "bad-config-plants.csv"
    shutil.copy2(malformed_dataset_dir / "plants.csv", malformed_plants)
    _write_malformed_plants_csv(malformed_plants)
    payload["data"] = {
        "csv_dir": str(malformed_dataset_dir),
        "csv_files": {"plants": str(malformed_plants)},
    }

    rejected_schema = client.put("/api/settings/config", json={"config": payload})
    assert rejected_schema.status_code == 400
    assert "Dataset schema invalid for table 'plants'" in rejected_schema.json()["detail"]

    unchanged = load_config(config.settings_path)
    assert unchanged.appearance["light_theme"] == "vscode_light"
    assert unchanged.csv_dir_setting == "input/tables-extracted"
    assert unchanged.csv_files == {}

    rejected = client.put("/api/settings/config", json={"config": {"appearance": "bad"}})
    assert rejected.status_code == 400

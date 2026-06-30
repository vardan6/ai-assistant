"""FastAPI server on :9006; CLI and UI should consume this API."""
from __future__ import annotations

import base64
import copy
import json
import queue
import shutil
import tempfile
import threading
import zipfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import SecretStore, TraceEvent
from .ai.provider_registry import evict_model_cache
from .ai.session_store import SessionStore
from .chat_commands import CommandContext, build_command_registry
from .config import AppConfig, DEFAULT_SETTINGS, ROOT_DIR, load_config, save_config
from .data.source import TABLE_NAMES
from .pipeline import Pipeline, PipelineAnswer
from .provider_config import (
    export_config_payload,
    normalize_data_settings,
    prepare_import_config_payload,
    prepare_dataset_settings,
    redact_provider,
    update_appearance_settings,
    update_provider_settings,
    update_ui_settings,
)

WEB_DIR = Path(__file__).resolve().parent / "web"
MANAGED_DATASET_ROOT = ROOT_DIR / "data" / "managed_datasets"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict[str, Any]) -> Response:
        response = await super().get_response(path, scope)
        response.headers.update(NO_CACHE_HEADERS)
        return response


class ChatRequest(BaseModel):
    question: str
    provider_id: str = ""
    gating_mode: str = "gated"
    session_id: str = ""


class SessionCreateRequest(BaseModel):
    title: str = "New chat"


class SessionUpdateRequest(BaseModel):
    title: str = "New chat"


class SecretWriteRequest(BaseModel):
    value: str = Field(default="", min_length=0)


class ProviderSettingsRequest(BaseModel):
    llm_providers: list[dict[str, Any]]
    model_routing: dict[str, Any]


class UISettingsRequest(BaseModel):
    default_gating_mode: str = "gated"
    verbose_trace: bool = True
    use_reference_now_anchor: bool = True


class AppearanceSettingsRequest(BaseModel):
    theme_mode: str = "light"
    light_theme: str = "quiet_light"
    dark_theme: str = "vscode_dark"


class ConfigImportRequest(BaseModel):
    config: dict[str, Any]


class DatasetSettingsRequest(BaseModel):
    csv_dir: str = "input/tables-extracted"
    csv_files: dict[str, str] = Field(default_factory=dict)


class DatasetTableUploadRequest(BaseModel):
    filename: str = ""
    content: str = ""


class DatasetZipImportRequest(BaseModel):
    filename: str = ""
    content_base64: str = ""


class CommandExecuteRequest(BaseModel):
    command: str
    session_id: str = ""


def _config_path_for_storage(path: Path) -> str:
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(path)


def _dataset_settings_payload(config: AppConfig) -> dict[str, Any]:
    return {
        "csv_dir": config.csv_dir_setting,
        "csv_files": {
            table_name: config.csv_files.get(table_name, "")
            for table_name in TABLE_NAMES
        },
    }


def _resolve_storage_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def _is_managed_dataset_path(path: Path) -> bool:
    try:
        path.relative_to(MANAGED_DATASET_ROOT)
    except ValueError:
        return False
    return True


def _managed_dataset_refs(config: AppConfig) -> set[Path]:
    refs: set[Path] = set()
    csv_dir_setting = str(config.csv_dir_setting or "").strip()
    if csv_dir_setting:
        csv_dir = _resolve_storage_path(csv_dir_setting)
        if _is_managed_dataset_path(csv_dir):
            refs.add(csv_dir)
    for path_value in config.csv_files.values():
        clean = str(path_value or "").strip()
        if not clean:
            continue
        path = _resolve_storage_path(clean)
        if _is_managed_dataset_path(path):
            refs.add(path)
    return refs


def _prune_superseded_managed_datasets(previous: AppConfig, current: AppConfig) -> None:
    stale_refs = sorted(
        _managed_dataset_refs(previous) - _managed_dataset_refs(current),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for path in stale_refs:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def create_app(
    config: AppConfig | None = None,
    *,
    pipeline: Pipeline | None = None,
    session_store: SessionStore | None = None,
    secret_store: SecretStore | None = None,
) -> FastAPI:
    app = FastAPI(title="Solar AI Assistant", version="0.1.0")
    app.mount("/assets", NoCacheStaticFiles(directory=WEB_DIR / "assets"), name="assets")
    cfg = config or load_config()
    secrets = secret_store or SecretStore(cfg.llm_secrets_db_path)
    sessions = session_store or SessionStore(cfg.ai_sessions_db_path)
    live_pipeline = pipeline or Pipeline(cfg, secret_resolver=secrets.get)
    command_registry = build_command_registry()

    def serialize_answer(result: PipelineAnswer) -> dict[str, Any]:
        return {
            "answer": result.answer,
            "intent": result.intent,
            "intent_meta": result.intent_meta,
            "tool_calls": [asdict(call) for call in result.tool_calls],
            "trace_events": [event.as_dict() for event in result.trace_events],
            "gating_mode": result.gating_mode,
            "bound_tools": result.bound_tools,
            "fast_path": result.fast_path,
            "iterations": result.iterations,
            "stop_reason": result.stop_reason,
            "provider_id": result.provider_id,
            "telemetry": result.telemetry.as_dict(),
        }

    def build_dataset_payload(*, validation_error: str = "") -> dict[str, Any]:
        csv_files = cfg.csv_files
        resolved_paths = cfg.resolved_csv_paths()
        return {
            "config": {
                "csv_dir": cfg.csv_dir_setting,
                "csv_files": {table_name: csv_files.get(table_name, "") for table_name in TABLE_NAMES},
            },
            "defaults": normalize_data_settings(copy.deepcopy(DEFAULT_SETTINGS["data"])),
            "status": {
                "dataset_today": live_pipeline.dataset_today.isoformat(),
                "csv_dir_resolved": str(cfg.csv_dir),
                "settings_path": str(cfg.settings_path),
                "validation_error": validation_error,
                "tables": [
                    {
                        "name": table_name,
                        "override_path": csv_files.get(table_name, ""),
                        "resolved_path": str(resolved_paths[table_name]),
                        "exists": resolved_paths[table_name].exists(),
                        "source": "override" if csv_files.get(table_name, "") else "default",
                    }
                    for table_name in TABLE_NAMES
                ],
            },
        }

    def validate_pipeline(candidate_cfg: AppConfig) -> Pipeline:
        try:
            return Pipeline(candidate_cfg, secret_resolver=secrets.get)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Dataset validation failed: {exc}") from exc

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "dataset_today": live_pipeline.dataset_today.isoformat(),
            "reference_now": live_pipeline.reference_now.isoformat(),
            "use_reference_now_anchor": cfg.use_reference_now_anchor,
        }

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html", headers=NO_CACHE_HEADERS)

    @app.head("/")
    def index_head() -> Response:
        return Response(headers=NO_CACHE_HEADERS)

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/settings/providers")
    def get_provider_settings() -> dict[str, Any]:
        providers = [
            redact_provider(provider, has_secret=_has_secret(secrets, provider))
            for provider in cfg.llm_providers
        ]
        return {"llm_providers": providers, "model_routing": cfg.model_routing}

    @app.put("/api/settings/providers")
    def put_provider_settings(request: ProviderSettingsRequest) -> dict[str, Any]:
        nonlocal cfg, live_pipeline
        cfg = update_provider_settings(
            cfg,
            llm_providers=request.llm_providers,
            model_routing=request.model_routing,
        )
        evict_model_cache()
        live_pipeline = Pipeline(cfg, secret_resolver=secrets.get)
        providers = [
            redact_provider(provider, has_secret=_has_secret(secrets, provider))
            for provider in cfg.llm_providers
        ]
        return {"llm_providers": providers, "model_routing": cfg.model_routing}

    @app.get("/api/settings/ui")
    def get_ui_settings() -> dict[str, Any]:
        return {
            "default_gating_mode": cfg.default_gating_mode,
            "verbose_trace": cfg.verbose_trace,
            "use_reference_now_anchor": cfg.use_reference_now_anchor,
        }

    @app.put("/api/settings/ui")
    def put_ui_settings(request: UISettingsRequest) -> dict[str, Any]:
        nonlocal cfg
        cfg = update_ui_settings(
            cfg,
            ui={
                "default_gating_mode": request.default_gating_mode,
                "verbose_trace": request.verbose_trace,
                "use_reference_now_anchor": request.use_reference_now_anchor,
            },
        )
        return {
            "default_gating_mode": cfg.default_gating_mode,
            "verbose_trace": cfg.verbose_trace,
            "use_reference_now_anchor": cfg.use_reference_now_anchor,
        }

    @app.get("/api/settings/appearance")
    def get_appearance_settings() -> dict[str, Any]:
        return cfg.appearance

    @app.put("/api/settings/appearance")
    def put_appearance_settings(request: AppearanceSettingsRequest) -> dict[str, Any]:
        nonlocal cfg
        try:
            cfg = update_appearance_settings(
                cfg,
                appearance={
                    "theme_mode": request.theme_mode,
                    "light_theme": request.light_theme,
                    "dark_theme": request.dark_theme,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return cfg.appearance

    @app.get("/api/settings/dataset")
    def get_dataset_settings() -> dict[str, Any]:
        return build_dataset_payload()

    @app.put("/api/settings/dataset")
    def put_dataset_settings(request: DatasetSettingsRequest) -> dict[str, Any]:
        nonlocal cfg, live_pipeline
        try:
            candidate_cfg = prepare_dataset_settings(
                cfg,
                data={
                    "csv_dir": request.csv_dir,
                    "csv_files": request.csv_files,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        candidate_pipeline = validate_pipeline(candidate_cfg)
        previous_cfg = cfg
        cfg = save_config(candidate_cfg)
        live_pipeline = candidate_pipeline
        _prune_superseded_managed_datasets(previous_cfg, cfg)
        return build_dataset_payload()

    @app.post("/api/settings/dataset/reload")
    def reload_dataset_settings() -> dict[str, Any]:
        nonlocal live_pipeline
        live_pipeline = validate_pipeline(cfg)
        return build_dataset_payload()

    @app.post("/api/settings/dataset/reset")
    def reset_dataset_settings() -> dict[str, Any]:
        nonlocal cfg, live_pipeline
        candidate_cfg = prepare_dataset_settings(cfg, data=copy.deepcopy(DEFAULT_SETTINGS["data"]))
        candidate_pipeline = validate_pipeline(candidate_cfg)
        previous_cfg = cfg
        cfg = save_config(candidate_cfg)
        live_pipeline = candidate_pipeline
        _prune_superseded_managed_datasets(previous_cfg, cfg)
        return build_dataset_payload()

    @app.post("/api/settings/dataset/upload/{table_name}")
    def upload_dataset_table(table_name: str, request: DatasetTableUploadRequest) -> dict[str, Any]:
        nonlocal cfg, live_pipeline
        if table_name not in TABLE_NAMES:
            raise HTTPException(status_code=404, detail=f"Unknown dataset table '{table_name}'.")
        if not request.filename or not request.content:
            raise HTTPException(status_code=400, detail="Dataset upload requires a CSV file.")
        managed_dir = MANAGED_DATASET_ROOT / "overrides"
        managed_dir.mkdir(parents=True, exist_ok=True)
        managed_path = managed_dir / f"{table_name}-{uuid4().hex}.csv"
        with tempfile.TemporaryDirectory(prefix=f"dataset-upload-{table_name}-") as temp_dir:
            staged_path = Path(temp_dir) / f"{table_name}.csv"
            staged_path.write_text(request.content, encoding="utf-8")
            shutil.copy2(staged_path, managed_path)
        candidate_payload = _dataset_settings_payload(cfg)
        candidate_payload["csv_files"][table_name] = _config_path_for_storage(managed_path)
        try:
            candidate_cfg = prepare_dataset_settings(cfg, data=candidate_payload)
            candidate_pipeline = validate_pipeline(candidate_cfg)
        except HTTPException:
            managed_path.unlink(missing_ok=True)
            raise
        previous_cfg = cfg
        cfg = save_config(candidate_cfg)
        live_pipeline = candidate_pipeline
        _prune_superseded_managed_datasets(previous_cfg, cfg)
        return build_dataset_payload()

    @app.post("/api/settings/dataset/import-zip")
    def import_dataset_zip(request: DatasetZipImportRequest) -> dict[str, Any]:
        nonlocal cfg, live_pipeline
        if not request.filename or not request.content_base64:
            raise HTTPException(status_code=400, detail="Dataset import requires a .zip file.")
        required_files = {f"{table_name}.csv": table_name for table_name in TABLE_NAMES}
        with tempfile.TemporaryDirectory(prefix="dataset-import-") as temp_dir:
            temp_root = Path(temp_dir)
            archive_path = temp_root / "dataset.zip"
            extracted_dir = temp_root / "dataset"
            extracted_dir.mkdir(parents=True, exist_ok=True)
            try:
                archive_path.write_bytes(base64.b64decode(request.content_base64))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Dataset import failed: invalid base64 payload.") from exc
            try:
                with zipfile.ZipFile(archive_path) as archive:
                    members: dict[str, zipfile.ZipInfo] = {}
                    for info in archive.infolist():
                        if info.is_dir():
                            continue
                        basename = Path(info.filename).name.lower()
                        if basename in required_files:
                            if basename in members:
                                raise HTTPException(
                                    status_code=400,
                                    detail=f"Dataset import failed: duplicate '{basename}' found in zip.",
                                )
                            members[basename] = info
                    missing = sorted(set(required_files) - set(members))
                    if missing:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Dataset import failed: missing required CSVs: {', '.join(missing)}.",
                        )
                    for basename, table_name in required_files.items():
                        target_path = extracted_dir / f"{table_name}.csv"
                        with archive.open(members[basename]) as src, target_path.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
            except zipfile.BadZipFile as exc:
                raise HTTPException(status_code=400, detail="Dataset import failed: invalid zip archive.") from exc

            managed_dir = MANAGED_DATASET_ROOT / "imports" / f"dataset-{uuid4().hex}"
            shutil.copytree(extracted_dir, managed_dir)
        candidate_payload = {
            "csv_dir": _config_path_for_storage(managed_dir),
            "csv_files": {},
        }
        try:
            candidate_cfg = prepare_dataset_settings(cfg, data=candidate_payload)
            candidate_pipeline = validate_pipeline(candidate_cfg)
        except HTTPException:
            shutil.rmtree(managed_dir, ignore_errors=True)
            raise
        previous_cfg = cfg
        cfg = save_config(candidate_cfg)
        live_pipeline = candidate_pipeline
        _prune_superseded_managed_datasets(previous_cfg, cfg)
        return build_dataset_payload()

    @app.get("/api/settings/config")
    def get_config_payload() -> dict[str, Any]:
        return {"config": export_config_payload(cfg)}

    @app.get("/api/chat/commands")
    def list_chat_commands() -> dict[str, Any]:
        return {"commands": [spec.as_dict() for spec in command_registry.specs()]}

    @app.post("/api/chat/commands/execute")
    def execute_chat_command(request: CommandExecuteRequest) -> dict[str, Any]:
        try:
            spec, result = command_registry.execute(
                request.command,
                CommandContext(tool_registry=live_pipeline.tool_registry),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown command '/{exc.args[0]}'.") from exc
        payload = {
            "answer": result.content,
            "command": spec.as_dict(),
            "metadata": {
                **result.metadata,
                "command": spec.as_dict(),
            },
        }
        if request.session_id:
            _append_turn_or_404(sessions, request.session_id, request.command, payload["answer"], payload["metadata"])
        return payload

    @app.put("/api/settings/config")
    def put_config_payload(request: ConfigImportRequest) -> dict[str, Any]:
        nonlocal cfg, live_pipeline, secrets, sessions
        try:
            candidate_cfg = prepare_import_config_payload(cfg, payload=request.config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        validate_pipeline(candidate_cfg)
        previous_cfg = cfg
        cfg = save_config(candidate_cfg)
        secrets = SecretStore(cfg.llm_secrets_db_path)
        sessions = SessionStore(cfg.ai_sessions_db_path)
        evict_model_cache()
        live_pipeline = Pipeline(cfg, secret_resolver=secrets.get)
        _prune_superseded_managed_datasets(previous_cfg, cfg)
        providers = [
            redact_provider(provider, has_secret=_has_secret(secrets, provider))
            for provider in cfg.llm_providers
        ]
        return {
            "config": export_config_payload(cfg),
            "llm_providers": providers,
            "model_routing": cfg.model_routing,
            "ui": {
                "default_gating_mode": cfg.default_gating_mode,
                "verbose_trace": cfg.verbose_trace,
            },
            "appearance": cfg.appearance,
        }

    @app.put("/api/settings/secrets/{secret_ref}")
    def put_secret(secret_ref: str, request: SecretWriteRequest) -> dict[str, Any]:
        secrets.set(secret_ref, request.value)
        evict_model_cache()
        return {"secret_ref": secret_ref, "stored": True}

    @app.delete("/api/settings/secrets/{secret_ref}")
    def delete_secret(secret_ref: str) -> dict[str, Any]:
        secrets.delete(secret_ref)
        evict_model_cache()
        return {"secret_ref": secret_ref, "stored": False}

    @app.get("/api/sessions")
    def list_sessions() -> dict[str, Any]:
        return {"sessions": sessions.list_sessions()}

    @app.post("/api/sessions")
    def create_session(request: SessionCreateRequest) -> dict[str, Any]:
        return sessions.create_session(title=request.title)

    @app.patch("/api/sessions/{session_id}")
    def update_session(session_id: str, request: SessionUpdateRequest) -> dict[str, Any]:
        try:
            sessions.update_session_title(session_id, title=request.title)
            return sessions.get_session_summary(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        try:
            return sessions.get_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: str) -> dict[str, Any]:
        try:
            sessions.delete_session(session_id)
            return {"deleted": True, "session_id": session_id}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/chat")
    def chat(request: ChatRequest) -> dict[str, Any]:
        try:
            result = live_pipeline.answer(
                request.question,
                provider_id=request.provider_id,
                gating_mode=request.gating_mode,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = serialize_answer(result)
        if request.session_id:
            _append_turn_or_404(sessions, request.session_id, request.question, payload)
        return payload

    @app.post("/api/chat/stream")
    def stream_chat(request: ChatRequest) -> StreamingResponse:
        events: queue.Queue[dict[str, Any] | None] = queue.Queue()

        def run() -> None:
            try:
                result = live_pipeline.answer(
                    request.question,
                    provider_id=request.provider_id,
                    gating_mode=request.gating_mode,
                    event_handler=lambda event: events.put({"type": "trace", "event": event.as_dict()}),
                )
                payload = serialize_answer(result)
                if request.session_id:
                    _append_turn_or_404(sessions, request.session_id, request.question, payload)
                events.put({"type": "final", "response": payload})
            except Exception as exc:  # surfaced in stream payload
                events.put({"type": "error", "error": str(exc)})
            finally:
                events.put(None)

        threading.Thread(target=run, daemon=True).start()

        def iterator():
            while True:
                item = events.get()
                if item is None:
                    break
                yield json.dumps(item, separators=(",", ":"), default=_json_default) + "\n"

        return StreamingResponse(iterator(), media_type="application/x-ndjson")

    return app


def _append_turn_or_404(
    sessions: SessionStore,
    session_id: str,
    question: str,
    payload: dict[str, Any] | str,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        sessions.append_turn(
            session_id,
            question=question,
            answer=str(payload.get("answer", "")) if isinstance(payload, dict) else str(payload),
            metadata=payload if isinstance(payload, dict) else (metadata or {}),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _has_secret(secrets: SecretStore, provider: dict[str, Any]) -> bool:
    auth_mode = str(provider.get("auth_mode", "env_var"))
    secret_ref = str(provider.get("secret_ref", "")).strip()
    return auth_mode == "stored_secret" and bool(secret_ref) and secrets.has(secret_ref)


def _json_default(value: Any) -> Any:
    if isinstance(value, TraceEvent):
        return value.as_dict()
    if is_dataclass(value):
        return asdict(value)
    return str(value)


app = create_app()

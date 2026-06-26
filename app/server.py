"""FastAPI server on :9006; CLI and UI should consume this API."""
from __future__ import annotations

import json
import queue
import threading
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import SecretStore, TraceEvent
from .ai.provider_registry import evict_model_cache
from .ai.session_store import SessionStore
from .config import AppConfig, load_config
from .pipeline import Pipeline, PipelineAnswer
from .provider_config import redact_provider, update_provider_settings, update_ui_settings

WEB_DIR = Path(__file__).resolve().parent / "web"


class ChatRequest(BaseModel):
    question: str
    provider_id: str = ""
    gating_mode: str = "gated"
    session_id: str = ""


class SessionCreateRequest(BaseModel):
    title: str = "New chat"


class SecretWriteRequest(BaseModel):
    value: str = Field(default="", min_length=0)


class ProviderSettingsRequest(BaseModel):
    llm_providers: list[dict[str, Any]]
    model_routing: dict[str, Any]


class UISettingsRequest(BaseModel):
    default_gating_mode: str = "gated"
    verbose_trace: bool = True


def create_app(
    config: AppConfig | None = None,
    *,
    pipeline: Pipeline | None = None,
    session_store: SessionStore | None = None,
    secret_store: SecretStore | None = None,
) -> FastAPI:
    app = FastAPI(title="Solar AI Assistant", version="0.1.0")
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
    cfg = config or load_config()
    secrets = secret_store or SecretStore(cfg.llm_secrets_db_path)
    sessions = session_store or SessionStore(cfg.ai_sessions_db_path)
    live_pipeline = pipeline or Pipeline(cfg, secret_resolver=secrets.get)

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
            "provider_id": result.provider_id,
            "telemetry": result.telemetry.as_dict(),
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "dataset_today": live_pipeline.dataset_today.isoformat()}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

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
        }

    @app.put("/api/settings/ui")
    def put_ui_settings(request: UISettingsRequest) -> dict[str, Any]:
        nonlocal cfg
        cfg = update_ui_settings(
            cfg,
            ui={
                "default_gating_mode": request.default_gating_mode,
                "verbose_trace": request.verbose_trace,
            },
        )
        return {
            "default_gating_mode": cfg.default_gating_mode,
            "verbose_trace": cfg.verbose_trace,
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

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        try:
            return sessions.get_session(session_id)
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
    payload: dict[str, Any],
) -> None:
    try:
        sessions.append_turn(
            session_id,
            question=question,
            answer=str(payload.get("answer", "")),
            metadata=payload,
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

"""Application config — JSON file with deep-merge over baked-in defaults.

Pattern carried from the reference `gcs_server/config.py`: `common.local.json`
(gitignored, real values) is deep-merged over `common.example.json` (committed,
shareable), which is itself merged over `DEFAULT_SETTINGS`. Secrets never live
here — providers carry a `secret_ref` only (env var name or SecretStore key).
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_PATH = ROOT_DIR / "config" / "common.local.json"
FALLBACK_SETTINGS_PATH = ROOT_DIR / "config" / "common.example.json"

# Pre-seeded providers (ADR/design: OpenAI + Ollama). Refs only — no raw keys.
DEFAULT_LLM_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "openai-default",
        "display_name": "OpenAI",
        "provider_type": "openai",
        "model_id": "gpt-4o-mini",
        "auth_mode": "env_var",
        "secret_ref": "OPENAI_API_KEY",
        "base_url": "",
        "enabled": True,
    },
    {
        "id": "ollama-default",
        "display_name": "Ollama Local",
        "provider_type": "ollama",
        "model_id": "llama3:latest",
        "auth_mode": "none",
        "secret_ref": "",
        "base_url": "http://localhost:11434",
        "enabled": True,
    },
]

DEFAULT_SETTINGS: dict[str, Any] = {
    "llm_providers": copy.deepcopy(DEFAULT_LLM_PROVIDERS),
    # Route intent cheaply/local-first while keeping synthesis on the stronger
    # default provider when available.
    "model_routing": {
        "intent": {
            "primary_provider_id": "ollama-default",
            "fallback_provider_ids": ["openai-default"],
        },
        "synthesis": {
            "primary_provider_id": "openai-default",
            "fallback_provider_ids": ["ollama-default"],
        },
    },
    "data": {
        "csv_dir": "input/tables-extracted",
    },
    "logging": {
        "llm_secrets_db_path": "data/llm_secrets.sqlite3",
        "ai_sessions_db_path": "data/ai_sessions.sqlite3",
    },
    "server": {
        "host": "127.0.0.1",
        "port": 9006,
    },
    "ui": {
        "default_gating_mode": "gated",
        "verbose_trace": True,
    },
    "appearance": {
        "theme_mode": "light",
        "light_theme": "quiet_light",
        "dark_theme": "vscode_dark",
    },
}

APPEARANCE_THEME_MODES = {"light", "dark", "system"}
APPEARANCE_LIGHT_THEMES = {"vscode_light", "quiet_light", "cool_light", "sandstone_light"}
APPEARANCE_DARK_THEMES = {"vscode_dark", "graphite_dark", "midnight_dark", "amber_dark"}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


@dataclass(slots=True)
class AppConfig:
    raw: dict[str, Any]
    settings_path: Path

    @property
    def llm_providers(self) -> list[dict[str, Any]]:
        providers = self.raw.get("llm_providers", [])
        return providers if isinstance(providers, list) else []

    @property
    def model_routing(self) -> dict[str, Any]:
        routing = self.raw.get("model_routing", {})
        return routing if isinstance(routing, dict) else {}

    @property
    def data(self) -> dict[str, Any]:
        section = self.raw.get("data", {})
        return section if isinstance(section, dict) else {}

    @property
    def csv_dir(self) -> Path:
        configured = str(self.data.get("csv_dir", "input/tables-extracted")).strip()
        path = Path(configured)
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def logging(self) -> dict[str, Any]:
        section = self.raw.get("logging", {})
        return section if isinstance(section, dict) else {}

    @property
    def llm_secrets_db_path(self) -> Path:
        configured = str(self.logging.get("llm_secrets_db_path", "data/llm_secrets.sqlite3")).strip()
        path = Path(configured)
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def ai_sessions_db_path(self) -> Path:
        configured = str(self.logging.get("ai_sessions_db_path", "data/ai_sessions.sqlite3")).strip()
        path = Path(configured)
        return path if path.is_absolute() else ROOT_DIR / path

    @property
    def server(self) -> dict[str, Any]:
        section = self.raw.get("server", {})
        return section if isinstance(section, dict) else {}

    @property
    def server_host(self) -> str:
        return str(self.server.get("host", "127.0.0.1")).strip() or "127.0.0.1"

    @property
    def server_port(self) -> int:
        try:
            return int(self.server.get("port", 9006))
        except (TypeError, ValueError):
            return 9006

    @property
    def ui(self) -> dict[str, Any]:
        section = self.raw.get("ui", {})
        return section if isinstance(section, dict) else {}

    @property
    def default_gating_mode(self) -> str:
        value = str(self.ui.get("default_gating_mode", "gated")).strip().lower()
        return value if value in {"gated", "bind_all"} else "gated"

    @property
    def verbose_trace(self) -> bool:
        return bool(self.ui.get("verbose_trace", True))

    @property
    def appearance(self) -> dict[str, Any]:
        section = self.raw.get("appearance", {})
        merged = copy.deepcopy(DEFAULT_SETTINGS["appearance"])
        if isinstance(section, dict):
            merged.update({k: v for k, v in section.items() if k in merged})
        if str(merged.get("theme_mode")) not in APPEARANCE_THEME_MODES:
            merged["theme_mode"] = "light"
        if str(merged.get("light_theme")) not in APPEARANCE_LIGHT_THEMES:
            merged["light_theme"] = "quiet_light"
        if str(merged.get("dark_theme")) not in APPEARANCE_DARK_THEMES:
            merged["dark_theme"] = "vscode_dark"
        return merged


def load_config(path: str | Path | None = None) -> AppConfig:
    settings_path = Path(path) if path else DEFAULT_SETTINGS_PATH
    data: dict[str, Any] = {}
    if FALLBACK_SETTINGS_PATH.exists():
        with open(FALLBACK_SETTINGS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    if settings_path.exists():
        with open(settings_path, encoding="utf-8") as fh:
            data = _deep_merge(data, json.load(fh))
    merged = _deep_merge(DEFAULT_SETTINGS, data)
    providers = merged.get("llm_providers")
    if not isinstance(providers, list) or not providers:
        merged["llm_providers"] = copy.deepcopy(DEFAULT_LLM_PROVIDERS)
    return AppConfig(raw=merged, settings_path=settings_path)


def save_config(config: AppConfig, *, path: str | Path | None = None) -> AppConfig:
    settings_path = Path(path) if path else config.settings_path
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as fh:
        json.dump(config.raw, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return AppConfig(raw=copy.deepcopy(config.raw), settings_path=settings_path)

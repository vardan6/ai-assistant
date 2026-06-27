"""Normalization helpers for provider/settings CRUD."""
from __future__ import annotations

import copy
from typing import Any

from .config import (
    APPEARANCE_DARK_THEMES,
    APPEARANCE_LIGHT_THEMES,
    APPEARANCE_THEME_MODES,
    AppConfig,
    DEFAULT_SETTINGS,
    save_config,
)
from .data.source import TABLE_NAMES

SUPPORTED_PROVIDER_TYPES = {
    "openai",
    "anthropic",
    "google_gemini",
    "mistral",
    "cohere",
    "groq",
    "huggingface",
    "nvidia_nim",
    "ollama",
    "openai_compatible",
    "openrouter",
    "together",
    "lm_studio",
}
SUPPORTED_AUTH_MODES = {"env_var", "stored_secret", "none"}
SUPPORTED_GATING_MODES = {"gated", "bind_all"}


def normalize_provider(provider: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(provider, dict):
        raise ValueError("Provider must be an object.")
    normalized = {
        "id": str(provider.get("id", "")).strip(),
        "display_name": str(provider.get("display_name", "")).strip(),
        "provider_type": str(provider.get("provider_type", "")).strip(),
        "model_id": str(provider.get("model_id", "")).strip(),
        "auth_mode": str(provider.get("auth_mode", "env_var")).strip(),
        "secret_ref": str(provider.get("secret_ref", "")).strip(),
        "base_url": str(provider.get("base_url", "")).strip(),
        "context_window": None,
        "capabilities": [],
        "enabled": bool(provider.get("enabled", True)),
    }
    raw_context_window = provider.get("context_window")
    if raw_context_window not in ("", None):
        normalized["context_window"] = int(raw_context_window)
    raw_capabilities = provider.get("capabilities", [])
    if isinstance(raw_capabilities, list):
        normalized["capabilities"] = [str(item).strip() for item in raw_capabilities if str(item).strip()]
    if not normalized["id"]:
        raise ValueError("Provider id is required.")
    if not normalized["display_name"]:
        normalized["display_name"] = normalized["id"]
    if normalized["provider_type"] not in SUPPORTED_PROVIDER_TYPES:
        raise ValueError(f"Unsupported provider_type '{normalized['provider_type']}'.")
    if not normalized["model_id"]:
        raise ValueError("Provider model_id is required.")
    if normalized["auth_mode"] not in SUPPORTED_AUTH_MODES:
        raise ValueError(f"Unsupported auth_mode '{normalized['auth_mode']}'.")
    if normalized["auth_mode"] == "none":
        normalized["secret_ref"] = ""
    if normalized["context_window"] is not None and normalized["context_window"] < 0:
        raise ValueError("context_window must be >= 0.")
    return normalized


def normalize_provider_list(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for provider in providers:
        item = normalize_provider(provider)
        if item["id"] in seen:
            raise ValueError(f"Duplicate provider id '{item['id']}'.")
        seen.add(item["id"])
        normalized.append(item)
    if not normalized:
        raise ValueError("At least one provider is required.")
    return normalized


def normalize_model_routing(routing: dict[str, Any], provider_ids: set[str]) -> dict[str, Any]:
    if not isinstance(routing, dict):
        raise ValueError("model_routing must be an object.")
    normalized: dict[str, Any] = {}
    for purpose, raw_rule in routing.items():
        if not isinstance(raw_rule, dict):
            raise ValueError(f"Routing rule for '{purpose}' must be an object.")
        primary = str(raw_rule.get("primary_provider_id", "")).strip()
        fallbacks = [str(x).strip() for x in raw_rule.get("fallback_provider_ids", []) if str(x).strip()]
        for provider_id in [primary, *fallbacks]:
            if provider_id and provider_id not in provider_ids:
                raise ValueError(f"Routing for '{purpose}' references unknown provider '{provider_id}'.")
        normalized[str(purpose)] = {
            "primary_provider_id": primary,
            "fallback_provider_ids": fallbacks,
        }
    return normalized


def update_provider_settings(
    config: AppConfig,
    *,
    llm_providers: list[dict[str, Any]],
    model_routing: dict[str, Any],
) -> AppConfig:
    providers = normalize_provider_list(llm_providers)
    routing = normalize_model_routing(model_routing, {provider["id"] for provider in providers})
    updated = copy.deepcopy(config.raw)
    updated["llm_providers"] = providers
    updated["model_routing"] = routing
    return save_config(AppConfig(raw=updated, settings_path=config.settings_path))


def normalize_ui_settings(ui: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ui, dict):
        raise ValueError("ui must be an object.")
    default_gating_mode = str(ui.get("default_gating_mode", "gated")).strip().lower()
    if default_gating_mode not in SUPPORTED_GATING_MODES:
        raise ValueError(
            f"Unsupported default_gating_mode '{default_gating_mode}'."
        )
    return {
        "default_gating_mode": default_gating_mode,
        "verbose_trace": bool(ui.get("verbose_trace", True)),
    }


def update_ui_settings(
    config: AppConfig,
    *,
    ui: dict[str, Any],
) -> AppConfig:
    updated = copy.deepcopy(config.raw)
    updated["ui"] = normalize_ui_settings(ui)
    return save_config(AppConfig(raw=updated, settings_path=config.settings_path))


def normalize_appearance(appearance: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(appearance, dict):
        raise ValueError("appearance must be an object.")
    theme_mode = str(appearance.get("theme_mode", "light")).strip().lower()
    light_theme = str(appearance.get("light_theme", "quiet_light")).strip().lower()
    dark_theme = str(appearance.get("dark_theme", "vscode_dark")).strip().lower()
    if theme_mode not in APPEARANCE_THEME_MODES:
        raise ValueError(f"Unsupported theme_mode '{theme_mode}'.")
    if light_theme not in APPEARANCE_LIGHT_THEMES:
        raise ValueError(f"Unsupported light_theme '{light_theme}'.")
    if dark_theme not in APPEARANCE_DARK_THEMES:
        raise ValueError(f"Unsupported dark_theme '{dark_theme}'.")
    return {
        "theme_mode": theme_mode,
        "light_theme": light_theme,
        "dark_theme": dark_theme,
    }


def update_appearance_settings(
    config: AppConfig,
    *,
    appearance: dict[str, Any],
) -> AppConfig:
    updated = copy.deepcopy(config.raw)
    updated["appearance"] = normalize_appearance(appearance)
    return save_config(AppConfig(raw=updated, settings_path=config.settings_path))


def normalize_data_settings(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("data must be an object.")
    csv_dir = str(data.get("csv_dir", DEFAULT_SETTINGS["data"]["csv_dir"])).strip()
    if not csv_dir:
        raise ValueError("data.csv_dir is required.")
    raw_csv_files = data.get("csv_files", {})
    if raw_csv_files in (None, ""):
        raw_csv_files = {}
    if not isinstance(raw_csv_files, dict):
        raise ValueError("data.csv_files must be an object.")
    unknown_tables = sorted(set(raw_csv_files) - set(TABLE_NAMES))
    if unknown_tables:
        raise ValueError(f"Unknown dataset table overrides: {', '.join(unknown_tables)}.")
    csv_files: dict[str, str] = {}
    for table_name in TABLE_NAMES:
        value = str(raw_csv_files.get(table_name, "")).strip()
        if value:
            csv_files[table_name] = value
    return {
        "csv_dir": csv_dir,
        "csv_files": csv_files,
    }


def prepare_dataset_settings(
    config: AppConfig,
    *,
    data: dict[str, Any],
) -> AppConfig:
    updated = copy.deepcopy(config.raw)
    updated["data"] = normalize_data_settings(data)
    return AppConfig(raw=updated, settings_path=config.settings_path)


def update_dataset_settings(
    config: AppConfig,
    *,
    data: dict[str, Any],
) -> AppConfig:
    return save_config(prepare_dataset_settings(config, data=data))


def export_config_payload(config: AppConfig) -> dict[str, Any]:
    return {
        "llm_providers": normalize_provider_list(copy.deepcopy(config.llm_providers)),
        "model_routing": normalize_model_routing(copy.deepcopy(config.model_routing), {provider["id"] for provider in config.llm_providers}),
        "data": normalize_data_settings(copy.deepcopy(config.raw.get("data", DEFAULT_SETTINGS["data"]))),
        "logging": copy.deepcopy(config.raw.get("logging", DEFAULT_SETTINGS["logging"])),
        "server": copy.deepcopy(config.raw.get("server", DEFAULT_SETTINGS["server"])),
        "ui": normalize_ui_settings(copy.deepcopy(config.raw.get("ui", DEFAULT_SETTINGS["ui"]))),
        "appearance": normalize_appearance(copy.deepcopy(config.raw.get("appearance", DEFAULT_SETTINGS["appearance"]))),
    }


def normalize_imported_config(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("config must be an object.")
    providers = normalize_provider_list(payload.get("llm_providers", []))
    provider_ids = {provider["id"] for provider in providers}
    normalized = {
        "llm_providers": providers,
        "model_routing": normalize_model_routing(payload.get("model_routing", {}), provider_ids),
        "data": normalize_data_settings(payload.get("data", DEFAULT_SETTINGS["data"])),
        "logging": copy.deepcopy(payload.get("logging", DEFAULT_SETTINGS["logging"])),
        "server": copy.deepcopy(payload.get("server", DEFAULT_SETTINGS["server"])),
        "ui": normalize_ui_settings(payload.get("ui", DEFAULT_SETTINGS["ui"])),
        "appearance": normalize_appearance(payload.get("appearance", DEFAULT_SETTINGS["appearance"])),
    }
    for section in ("data", "logging", "server"):
        if not isinstance(normalized[section], dict):
            raise ValueError(f"{section} must be an object.")
    return normalized


def import_config_payload(
    config: AppConfig,
    *,
    payload: dict[str, Any],
) -> AppConfig:
    normalized = normalize_imported_config(payload)
    return save_config(AppConfig(raw=normalized, settings_path=config.settings_path))


def redact_provider(provider: dict[str, Any], *, has_secret: bool | None = None) -> dict[str, Any]:
    redacted = copy.deepcopy(provider)
    if has_secret is not None:
        redacted["has_secret"] = has_secret
    return redacted

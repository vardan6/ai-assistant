"""Normalization helpers for provider/settings CRUD."""
from __future__ import annotations

import copy
from typing import Any

from .config import AppConfig, save_config

SUPPORTED_PROVIDER_TYPES = {
    "openai",
    "anthropic",
    "google_gemini",
    "mistral",
    "groq",
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
        "enabled": bool(provider.get("enabled", True)),
    }
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


def redact_provider(provider: dict[str, Any], *, has_secret: bool | None = None) -> dict[str, Any]:
    redacted = copy.deepcopy(provider)
    if has_secret is not None:
        redacted["has_secret"] = has_secret
    return redacted

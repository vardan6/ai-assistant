"""Provider registry — builds langchain chat models from config, with caching.

Trimmed from the reference `gcs_server/ai/provider_registry.py`: chat models only
(no embeddings/RAG). Routing: `ollama` -> ChatOllama, `anthropic` -> ChatAnthropic,
everything else -> ChatOpenAI (+ base_url). Secrets resolve via env var or an
injected `secret_resolver` (SecretStore); raw keys never live in config.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Callable

# Provider types routed through the OpenAI-compatible ChatOpenAI client.
OPENAI_COMPATIBLE_PROVIDER_TYPES = {
    "openai",
    "google_gemini",
    "mistral",
    "cohere",
    "groq",
    "huggingface",
    "nvidia_nim",
    "openai_compatible",
    "openrouter",
    "together",
    "lm_studio",
}

_MODEL_CACHE: dict[str, Any] = {}


def evict_model_cache() -> None:
    """Clear the process-level model cache (call after provider config changes)."""
    _MODEL_CACHE.clear()


@dataclass(slots=True)
class ResolvedProvider:
    provider: dict[str, Any]
    model: Any


def resolve_provider(
    config: Any,
    *,
    purpose: str = "synthesis",
    provider_id: str = "",
    secret_resolver: Callable[[str], str] | None = None,
) -> ResolvedProvider:
    """Resolve the provider for a routing purpose (or an explicit provider_id)."""
    providers = [p for p in config.llm_providers if isinstance(p, dict)]
    provider = (
        _find_provider(providers, provider_id)
        if provider_id
        else _provider_from_routing(config.model_routing, providers, purpose)
    )
    if provider is None:
        raise ValueError(f"No LLM provider is configured for purpose '{purpose}'.")
    if not provider.get("enabled", True):
        name = provider.get("display_name") or provider.get("id")
        raise ValueError(f"LLM provider '{name}' is disabled.")
    return ResolvedProvider(
        provider=provider,
        model=_cached_chat_model(provider, secret_resolver=secret_resolver),
    )


def _provider_cache_key(
    provider: dict[str, Any],
    *,
    secret_resolver: Callable[[str], str] | None = None,
) -> str:
    relevant = {
        "id": provider.get("id"),
        "provider_type": provider.get("provider_type"),
        "model_id": provider.get("model_id"),
        "base_url": provider.get("base_url"),
        "auth_mode": provider.get("auth_mode"),
        "secret_ref": provider.get("secret_ref"),
    }
    auth_mode = str(provider.get("auth_mode", "env_var"))
    if auth_mode == "env_var":  # invalidate cache when the env key rotates
        relevant["_secret_val"] = os.getenv(str(provider.get("secret_ref", "")), "")
    elif auth_mode == "stored_secret" and secret_resolver is not None:
        relevant["_secret_val"] = secret_resolver(str(provider.get("secret_ref", "")))
    payload = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _cached_chat_model(provider: dict[str, Any], *, secret_resolver: Callable[[str], str] | None = None) -> Any:
    key = _provider_cache_key(provider, secret_resolver=secret_resolver)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = build_chat_model(provider, secret_resolver=secret_resolver)
    return _MODEL_CACHE[key]


def build_chat_model(provider: dict[str, Any], *, secret_resolver: Callable[[str], str] | None = None) -> Any:
    provider_type = str(provider.get("provider_type", "openai_compatible"))
    if provider_type == "ollama":
        return _build_ollama_chat_model(provider)
    if provider_type == "anthropic":
        return _build_anthropic_chat_model(provider, secret_resolver=secret_resolver)
    if provider_type not in OPENAI_COMPATIBLE_PROVIDER_TYPES:
        raise ValueError(f"Unsupported LLM provider type: {provider_type}")

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("langchain-openai is not installed. See requirements.txt.") from exc

    model_id = str(provider.get("model_id") or "").strip()
    if not model_id:
        raise ValueError("Selected LLM provider has no model_id.")
    kwargs: dict[str, Any] = {
        "model": model_id,
        "api_key": _api_key_for_provider(provider, secret_resolver=secret_resolver),
        "temperature": 0.2,
        "stream_usage": True,
    }
    base_url = str(provider.get("base_url") or "").strip()
    if base_url:
        kwargs["base_url"] = base_url.rstrip("/")
    return ChatOpenAI(**kwargs)


def _build_anthropic_chat_model(provider: dict[str, Any], *, secret_resolver: Callable[[str], str] | None = None) -> Any:
    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError as exc:
        raise RuntimeError("langchain-anthropic is not installed. See requirements.txt.") from exc
    model_id = str(provider.get("model_id") or "").strip()
    if not model_id:
        raise ValueError("Selected Anthropic provider has no model_id.")
    return ChatAnthropic(
        model=model_id,
        api_key=_api_key_for_provider(provider, secret_resolver=secret_resolver),
        temperature=0.2,
    )


def _build_ollama_chat_model(provider: dict[str, Any]) -> Any:
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:
        raise RuntimeError("langchain-ollama is not installed. See requirements.txt.") from exc
    model_id = str(provider.get("model_id") or "").strip()
    if not model_id:
        raise ValueError("Selected Ollama provider has no model_id.")
    kwargs: dict[str, Any] = {"model": model_id, "temperature": 0.2, "keep_alive": -1}
    base_url = str(provider.get("base_url") or "").strip()
    if base_url:
        kwargs["base_url"] = base_url.rstrip("/")
    return ChatOllama(**kwargs)


def _provider_from_routing(
    routing: dict[str, Any],
    providers: list[dict[str, Any]],
    purpose: str,
) -> dict[str, Any] | None:
    rule = routing.get(purpose, {}) if isinstance(routing, dict) else {}
    candidate_ids: list[str] = []
    if isinstance(rule, dict):
        primary = str(rule.get("primary_provider_id", "")).strip()
        fallbacks = [str(x).strip() for x in rule.get("fallback_provider_ids", []) if str(x).strip()]
        candidate_ids = [primary, *fallbacks]
    for candidate_id in candidate_ids:
        provider = _find_provider(providers, candidate_id)
        if provider and provider.get("enabled", True):
            return provider
    # Default: first enabled provider.
    return next((p for p in providers if p.get("enabled", True)), None)


def _find_provider(providers: list[dict[str, Any]], provider_id: str) -> dict[str, Any] | None:
    return next((p for p in providers if str(p.get("id")) == provider_id), None)


def _api_key_for_provider(provider: dict[str, Any], *, secret_resolver: Callable[[str], str] | None = None) -> str:
    auth_mode = str(provider.get("auth_mode", "env_var"))
    if auth_mode == "none":
        return "not-needed"
    secret_ref = str(provider.get("secret_ref", "")).strip()
    if not secret_ref:
        raise ValueError("Selected LLM provider has no secret_ref.")
    if auth_mode == "stored_secret":
        if secret_resolver is None:
            raise ValueError("Stored secret auth is not available in this runtime.")
        api_key = str(secret_resolver(secret_ref)).strip()
        if not api_key:
            raise ValueError("Stored secret value is empty.")
        return api_key
    # env_var
    api_key = os.getenv(secret_ref, "").strip()
    if not api_key:
        raise ValueError(f"Environment variable {secret_ref} is not set.")
    return api_key

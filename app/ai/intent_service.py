"""Intent service — LLM -> JSON classifier with a smalltalk fast-path and JSON repair.

Adapted from the reference `gcs_server/ai/intent_service.py`, reshaped to the
A/B/C intent schema. Returns the intent dict plus parse errors, latency, and the
provider name so the classification stays explicit and inspectable.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .usage_telemetry import model_name_from_model, usage_from_response
from .intent_prompt import build_intent_prompt
from .intent_schema import coerce_intent, make_empty_intent, validate_intent
from .smalltalk import is_smalltalk

_MAX_REPAIR_ATTEMPTS = 1


class IntentService:
    def parse(
        self,
        user_prompt: str,
        *,
        model: Any,
        context_summary: str = "",
    ) -> dict[str, Any]:
        """Classify a question into the A/B/C intent schema.

        Returns: intent, parse_errors, provider_name, latency_ms, fast_path.
        """
        clean = str(user_prompt or "").strip()
        if not clean:
            return _envelope(make_empty_intent(), ["empty prompt"], fast_path="empty")

        if is_smalltalk(clean):
            intent = make_empty_intent()
            intent["summary"] = "Smalltalk / greeting"
            intent["confidence"] = 1.0
            return _envelope(intent, [], fast_path="smalltalk")

        system = build_intent_prompt(context_summary)
        start = time.time()
        intent, errors, usage = _invoke_with_repair(model, system, clean, repair_attempts=_MAX_REPAIR_ATTEMPTS)
        latency_ms = int((time.time() - start) * 1000)

        return _envelope(
            intent,
            errors,
            provider_name=model_name_from_model(model),
            latency_ms=latency_ms,
            usage=usage,
        )


def _envelope(
    intent: dict[str, Any],
    errors: list[str],
    *,
    provider_name: str = "",
    latency_ms: int = 0,
    fast_path: str = "",
    usage: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "parse_errors": errors,
        "provider_name": provider_name,
        "latency_ms": latency_ms,
        "fast_path": fast_path,
        "usage": usage or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }


def _invoke_with_repair(model: Any, system: str, user: str, *, repair_attempts: int) -> tuple[dict[str, Any], list[str], dict[str, int]]:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    messages: list[Any] = [SystemMessage(content=system), HumanMessage(content=user)]
    raw = model.invoke(messages)
    usage = usage_from_response(raw)
    raw_text = str(getattr(raw, "content", raw) or "")
    intent, errors = _parse_intent_json(raw_text)
    if not errors:
        return intent, [], usage.as_dict()

    for _ in range(repair_attempts):
        repair = [
            *messages,
            AIMessage(content=raw_text),
            HumanMessage(content=(
                "Your previous response was not valid JSON or did not match the schema. "
                f"Errors: {'; '.join(errors)}. Return ONLY the corrected JSON object."
            )),
        ]
        raw = model.invoke(repair)
        usage = usage.add(usage_from_response(raw))
        raw_text = str(getattr(raw, "content", raw) or "")
        intent, errors = _parse_intent_json(raw_text)
        if not errors:
            return intent, [], usage.as_dict()
    return intent, errors, usage.as_dict()


def _parse_intent_json(text: str) -> tuple[dict[str, Any], list[str]]:
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"\s*```$", "", clean, flags=re.MULTILINE).strip()

    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        return make_empty_intent(), ["model output contained no JSON object"]
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return make_empty_intent(), [f"JSON parse error: {exc}"]
    if not isinstance(data, dict):
        return make_empty_intent(), ["parsed JSON is not an object"]

    errors = validate_intent(data)
    return coerce_intent(data), errors

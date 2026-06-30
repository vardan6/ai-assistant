"""Lane C agent-context helpers used by the runtime transition."""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

TurnKind = Literal[
    "data_question",
    "follow_up",
    "dispute_correction",
    "clarification",
    "prior_answer_meta",
    "smalltalk",
    "command",
    "out_of_scope",
]

PriorAnswerVerdictStatus = Literal["correct", "wrong", "incomplete"]

_PLANT_NAMES = (
    "Rajasthan Solar Park",
    "Gujarat Solar Farm",
    "Tamil Nadu PV Plant",
)
_AMBIGUOUS_PLANT_QUESTIONS = {
    "how is the plant doing?",
    "how is the plant doing",
}


class PromptHistoryMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class SessionHistoryMessage(TypedDict, total=False):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    metadata: dict[str, Any]


class PriorAnswerVerdict(TypedDict, total=False):
    status: PriorAnswerVerdictStatus
    referenced_message_id: int
    referenced_claim: str
    predicate_summary: str
    explanation: str
    tool_names: list[str]
    entity_ids: list[str]
    numbers: list[float]
    evidence_fingerprint_sha256: str


class AgentContext(TypedDict):
    session_id: str
    latest_user_message: str
    history_window: list[SessionHistoryMessage]
    prompt_history: list[PromptHistoryMessage]


def load_session_context(store: Any, session_id: str, latest_user_message: str) -> AgentContext:
    return {
        "session_id": session_id,
        "latest_user_message": latest_user_message,
        "history_window": list(store.load_history_window(session_id)),
        "prompt_history": list(store.load_prompt_history(session_id)),
    }


def summarize_prompt_history(prompt_history: list[PromptHistoryMessage] | None, *, limit: int = 4) -> str:
    if not prompt_history:
        return ""
    window = [item for item in prompt_history if item.get("content", "").strip()][-limit:]
    if not window:
        return ""
    return "\n".join(
        f"{item.get('role', 'user')}: {str(item.get('content', '')).strip()}"
        for item in window
    )


def recent_plant_name(prompt_history: list[PromptHistoryMessage] | None) -> str:
    if not prompt_history:
        return ""
    for item in reversed(prompt_history):
        content = str(item.get("content", ""))
        for plant_name in _PLANT_NAMES:
            if plant_name.lower() in content.lower():
                return plant_name
    return ""


def can_resolve_ambiguous_plant(prompt_history: list[PromptHistoryMessage] | None) -> bool:
    return bool(recent_plant_name(prompt_history))


def resolve_follow_up_question(question: str, prompt_history: list[PromptHistoryMessage] | None) -> str:
    clean = " ".join(str(question or "").split()).strip()
    if not clean:
        return ""

    plant_name = recent_plant_name(prompt_history)
    clean_lower = clean.lower()
    previous_user = _latest_message(prompt_history, role="user")
    previous_assistant = _latest_message(prompt_history, role="assistant")

    if clean_lower in _AMBIGUOUS_PLANT_QUESTIONS and plant_name:
        return f"How is {plant_name} doing?"

    if clean_lower.startswith(("and ", "what about ", "how about ")):
        anchor = previous_user or previous_assistant
        if anchor:
            return f"{anchor} Follow-up: {clean}"

    if any(token in clean_lower for token in ("those", "that one", "same one", "previous", "earlier")):
        anchor_parts = [part for part in (previous_user, previous_assistant) if part]
        if anchor_parts:
            return " ".join([*anchor_parts, f"Follow-up question: {clean}"])

    if prompt_history:
        summary = summarize_prompt_history(prompt_history, limit=3)
        if summary:
            return f"Recent context:\n{summary}\nLatest follow-up: {clean}"
    return clean


def last_assistant_message(history_window: list[SessionHistoryMessage] | None) -> SessionHistoryMessage | None:
    if not history_window:
        return None
    for item in reversed(history_window):
        if item.get("role") == "assistant":
            return item
    return None


def build_prior_answer_verdict(
    *,
    history_window: list[SessionHistoryMessage] | None,
    predicate_summary: str,
    tool_calls: list[Any],
) -> PriorAnswerVerdict:
    referenced = last_assistant_message(history_window)
    referenced_claim = str(referenced.get("content", "")).strip() if referenced else ""
    referenced_message_id = int(referenced["id"]) if referenced and "id" in referenced else 0
    metadata = referenced.get("metadata") if referenced else {}
    evidence_fingerprint = ""
    if isinstance(metadata, dict):
        stored_fingerprint = metadata.get("evidence_fingerprint")
        if isinstance(stored_fingerprint, dict):
            evidence_fingerprint = str(stored_fingerprint.get("sha256", "")).strip()

    tool_names = [str(getattr(call, "name", "")).strip() for call in tool_calls if str(getattr(call, "name", "")).strip()]
    entity_ids = _extract_entity_ids(tool_calls)
    numbers = _extract_numbers(tool_calls)
    status = _classify_verdict(referenced_claim, entity_ids=entity_ids, numbers=numbers)

    verdict: PriorAnswerVerdict = {
        "status": status,
        "referenced_claim": referenced_claim or "No prior assistant answer was available to re-check.",
        "predicate_summary": predicate_summary.strip() or "Re-check the prior claim against fresh tool evidence.",
        "explanation": _verdict_explanation(status, entity_ids=entity_ids, numbers=numbers),
        "tool_names": tool_names,
        "entity_ids": entity_ids,
        "numbers": numbers,
    }
    if referenced_message_id:
        verdict["referenced_message_id"] = referenced_message_id
    if evidence_fingerprint:
        verdict["evidence_fingerprint_sha256"] = evidence_fingerprint
    return verdict


def _latest_message(prompt_history: list[PromptHistoryMessage] | None, *, role: str) -> str:
    if not prompt_history:
        return ""
    for item in reversed(prompt_history):
        if item.get("role") == role and str(item.get("content", "")).strip():
            return str(item["content"]).strip()
    return ""


def _extract_entity_ids(tool_calls: list[Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for call in tool_calls:
        result = getattr(call, "result", None)
        if not isinstance(result, dict):
            continue
        for key in ("matched_inverter_ids", "anomaly_ids"):
            values = result.get(key)
            if isinstance(values, list):
                for value in values:
                    text = str(value).strip()
                    if text and text not in seen:
                        seen.add(text)
                        found.append(text)
        anomalies = result.get("anomalies")
        if isinstance(anomalies, list):
            for item in anomalies:
                if not isinstance(item, dict):
                    continue
                for field in ("inverter_id", "plant_id", "anomaly_id"):
                    text = str(item.get(field, "")).strip()
                    if text and text not in seen:
                        seen.add(text)
                        found.append(text)
    return found


def _extract_numbers(tool_calls: list[Any]) -> list[float]:
    found: list[float] = []
    seen: set[float] = set()
    for call in tool_calls:
        result = getattr(call, "result", None)
        if not isinstance(result, dict):
            continue
        for number in _extract_numbers_from_value(result):
            rounded = round(float(number), 4)
            if rounded not in seen:
                seen.add(rounded)
                found.append(rounded)
    return found


def _extract_numbers_from_value(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        clean = value.strip().replace(",", "")
        if re.fullmatch(r"-?\d+(?:\.\d+)?", clean):
            return [float(clean)]
        return []
    if isinstance(value, dict):
        numbers: list[float] = []
        for nested in value.values():
            numbers.extend(_extract_numbers_from_value(nested))
        return numbers
    if isinstance(value, list):
        numbers: list[float] = []
        for nested in value:
            numbers.extend(_extract_numbers_from_value(nested))
        return numbers
    return []


def _classify_verdict(referenced_claim: str, *, entity_ids: list[str], numbers: list[float]) -> PriorAnswerVerdictStatus:
    clean_claim = referenced_claim.lower().strip()
    if not clean_claim:
        return "incomplete"
    entity_tokens = [token.lower() for token in entity_ids]
    number_tokens = _number_tokens(numbers)
    if not entity_tokens and not number_tokens:
        return "incomplete"
    entity_hits = [token for token in entity_tokens if token in clean_claim]
    number_hits = [token for token in number_tokens if token in clean_claim]
    if not entity_hits and not number_hits:
        return "wrong"
    if entity_tokens and len(entity_hits) == len(entity_tokens) and (not number_tokens or bool(number_hits)):
        return "correct"
    if number_tokens and len(number_hits) == len(number_tokens):
        return "correct"
    return "incomplete"


def _number_tokens(numbers: list[float]) -> list[str]:
    tokens: list[str] = []
    for number in numbers:
        tokens.append(str(int(number)) if float(number).is_integer() else str(number))
    return tokens


def _verdict_explanation(status: PriorAnswerVerdictStatus, *, entity_ids: list[str], numbers: list[float]) -> str:
    if status == "wrong":
        return "Fresh tool evidence did not support the referenced claim."
    if status == "correct":
        return "Fresh tool evidence matched the referenced claim."
    details: list[str] = []
    if entity_ids:
        details.append(f"entity_ids={', '.join(entity_ids[:4])}")
    if numbers:
        details.append(f"numbers={', '.join(str(value) for value in numbers[:4])}")
    suffix = f" Evidence: {'; '.join(details)}." if details else ""
    return f"The prior answer could only be partially checked from the available history.{suffix}"

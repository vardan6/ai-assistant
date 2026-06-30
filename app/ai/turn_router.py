"""Turn routing for the Lane C runtime transition.

This keeps the current single intent-classification call, but adds an explicit
router artifact so later LangGraph nodes can branch on `turn_kind`.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from .agent_graph import can_resolve_ambiguous_plant
from .intent_schema import make_empty_intent
from .smalltalk import is_smalltalk

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

_FOLLOW_UP_PREFIXES = (
    "and ",
    "what about ",
    "how about ",
    "what about that",
    "what about it",
    "and what about ",
    "what else ",
)
_AMBIGUOUS_PLANT_QUESTIONS = {
    "how is the plant doing?",
    "how is the plant doing",
}
_DISPUTE_PATTERNS = (
    "your answer was wrong",
    "your previous answer was wrong",
    "that answer was wrong",
    "that answer looks wrong",
    "that answer seems wrong",
    "that was wrong",
    "that's wrong",
    "you are wrong",
    "you're wrong",
    "incorrect",
    "not right",
)
_PRIOR_ANSWER_META_PATTERNS = (
    "what did you say",
    "what was your previous answer",
    "what was your last answer",
    "what was that plant again",
    "what was that inverter again",
    "was your previous answer right",
    "was your answer right",
    "did you answer",
)


def route_local_turn(question: str, *, prompt_history: list[dict[str, str]] | None = None) -> dict[str, Any] | None:
    clean = str(question or "").strip()
    clean_lower = clean.lower()
    if not clean:
        return {
            "turn_kind": "command",
            "intent": make_empty_intent(),
            "parse_errors": ["empty prompt"],
            "fast_path": "empty",
        }

    if clean.startswith("/"):
        intent = make_empty_intent()
        intent["summary"] = "Slash command"
        intent["confidence"] = 1.0
        return {
            "turn_kind": "command",
            "intent": intent,
            "parse_errors": [],
            "fast_path": "command",
        }

    if clean_lower in _AMBIGUOUS_PLANT_QUESTIONS and not can_resolve_ambiguous_plant(prompt_history):
        intent = make_empty_intent()
        intent["summary"] = "Ambiguous plant status question"
        intent["confidence"] = 1.0
        return {
            "turn_kind": "clarification",
            "intent": intent,
            "parse_errors": [],
            "fast_path": "ambiguous_plant",
        }

    if is_smalltalk(clean):
        intent = make_empty_intent()
        intent["summary"] = "Smalltalk / greeting"
        intent["confidence"] = 1.0
        return {
            "turn_kind": "smalltalk",
            "intent": intent,
            "parse_errors": [],
            "fast_path": "smalltalk",
        }
    return None


def infer_turn_kind(
    question: str,
    *,
    intent: dict[str, Any],
    prompt_history: list[dict[str, str]] | None = None,
) -> TurnKind:
    clean = str(question or "").strip().lower()
    if _looks_like_dispute(clean):
        return "dispute_correction"
    if any(pattern in clean for pattern in _PRIOR_ANSWER_META_PATTERNS):
        return "prior_answer_meta"
    if _looks_like_follow_up(clean, prompt_history=prompt_history):
        return "follow_up"
    if bool(intent.get("out_of_scope")):
        return "out_of_scope"
    return "data_question"


def is_tool_free_turn(turn_kind: TurnKind) -> bool:
    return turn_kind in {"smalltalk", "command", "clarification", "prior_answer_meta"}


def build_tool_free_reply(turn_kind: TurnKind, *, fast_path: str) -> str:
    if fast_path == "smalltalk":
        return (
            "Hi! I can answer questions about the solar plants, inverters, generation, "
            "alerts, anomalies, and maintenance. What would you like to know?"
        )
    if fast_path == "ambiguous_plant":
        return (
            "Which plant do you mean? The dataset has Rajasthan Solar Park, Gujarat Solar Farm, "
            "and Tamil Nadu PV Plant."
        )
    if fast_path == "empty":
        return "Please ask a question about the solar operations dataset."
    if fast_path == "command":
        return "Slash commands should be sent through the chat command endpoint, not the data pipeline."
    if turn_kind == "prior_answer_meta":
        return (
            "I can revisit prior answers once the session-aware meta path is wired. "
            "For now, restate the data question you want checked."
        )
    return "Please clarify the plant, inverter, metric, or time range you want me to check."


def _looks_like_follow_up(clean: str, *, prompt_history: list[dict[str, str]] | None = None) -> bool:
    if clean in _AMBIGUOUS_PLANT_QUESTIONS and can_resolve_ambiguous_plant(prompt_history):
        return True
    if any(clean.startswith(prefix) for prefix in _FOLLOW_UP_PREFIXES):
        return True
    if re.fullmatch(r"(and|what about|how about)\b.*", clean):
        return True
    return bool(re.search(r"\b(previous|earlier|same one|that one|those)\b", clean))


def _looks_like_dispute(clean: str) -> bool:
    if any(pattern in clean for pattern in _DISPUTE_PATTERNS):
        return True
    return bool(re.search(r"\b(?:that|your|previous)\s+answer\s+(?:looks|seems)\s+wrong\b", clean))

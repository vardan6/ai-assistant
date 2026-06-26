"""Smalltalk fast-path — greetings/acknowledgements short-circuit before LLM+tools.

Carried from the reference `smalltalk_patterns.py`. Normalize then exact-match
against a small set, so "Hi!" and "how are you ?" both hit without a model call.
"""
from __future__ import annotations

import re

MAX_SMALLTALK_CHARS = 60

SMALLTALK_SET: frozenset[str] = frozenset({
    # greetings
    "hi", "hello", "hey", "yo", "sup", "hiya", "hi hi", "hey hey",
    "good morning", "good afternoon", "good evening", "good day",
    # social questions
    "how are you", "how are you doing", "hows it going", "how's it going",
    # acknowledgements / reactions
    "thanks", "thank you", "thx", "ty",
    "ok", "okay", "alright", "cool", "got it", "great", "nice",
    "sounds good", "perfect",
    # closings
    "bye", "goodbye", "see you", "cheers",
})

_PUNCT_STRIP_RE = re.compile(r"^[!.,?;:]+|[!.,?;:]+$")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_for_smalltalk(content: str) -> str:
    s = content.lower().strip()
    s = _WHITESPACE_RE.sub(" ", s)
    s = _PUNCT_STRIP_RE.sub("", s).strip()
    return s


def is_smalltalk(content: str) -> bool:
    if len(content) > MAX_SMALLTALK_CHARS:
        return False
    return normalize_for_smalltalk(content) in SMALLTALK_SET

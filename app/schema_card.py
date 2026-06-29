"""Schema-card generator sourced from docs/dataset-analysis.md."""
from __future__ import annotations

import re
from pathlib import Path

from .config import ROOT_DIR

DATASET_ANALYSIS_PATH = ROOT_DIR / "docs" / "dataset-analysis.md"
_SECTION_HEADINGS = (
    "Join cardinality (fan-out)",
    "Entity resolver index",
    "Vocabulary coverage map",
    "Measure semantics (aggregation rules)",
)


def build_schema_card(path: Path = DATASET_ANALYSIS_PATH) -> str:
    text = path.read_text(encoding="utf-8")
    sections = [f"## {heading}\n{_extract_section(text, heading)}" for heading in _SECTION_HEADINGS]
    joined = "\n\n".join(sections)
    return (
        "Schema card (generated from docs/dataset-analysis.md; source of truth for relationships, "
        "resolver facts, exact vocabulary, and measure reducers).\n\n"
        f"{joined}"
    )


def _extract_section(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        raise ValueError(f"Missing schema-card section in dataset analysis: {heading}")
    return match.group("body").strip()

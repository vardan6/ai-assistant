"""Replay harness for CLI/API case validation against the oracle."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request

from scripts.golden_answers import build as build_oracle


GATE1_CASE_IDS: tuple[str, ...] = (
    "D1",
    "D2",
    "D3",
    "D4",
    "D5",
    "D6",
    "A1",
    "A2",
    "A3",
    "B1",
    "B2",
    "B3",
    "C1",
    "C2",
    "C3",
)

GATE2A_CASE_IDS: tuple[str, ...] = (
    "P2",
    "P3",
    "P4",
    "P5",
    "I2",
    "I3",
    "I4",
    "I5",
    "G2",
    "G3",
    "G5",
    "G6",
    "W1",
    "W2",
    "W3",
    "W4",
    "AL2",
    "AL3",
)

GATE2B_CASE_IDS: tuple[str, ...] = (
    "AL4",
    "AL6",
    "M1",
    "M2",
    "M3",
    "M4",
    "M5",
    "AN3",
    "AN4",
    "AN5",
    "AN7",
    "X1",
    "X2",
    "X3",
    "X4",
    "X5",
    "X6",
    "X7",
)

GATE2_CASE_IDS: tuple[str, ...] = GATE2A_CASE_IDS + GATE2B_CASE_IDS

GATE2_TRANSCRIPT_IDS: tuple[str, ...] = (
    "MT-D3-FOLLOWUP",
    "MT-D3-DISPUTE",
    "MT-PRIOR-ANSWER",
    "MT-RESOLVED-AMBIGUITY",
)


@dataclass(frozen=True)
class RequiredToolArgs:
    tool: str
    args: dict[str, Any]


@dataclass(frozen=True)
class RequiredToolResultField:
    tool: str
    path: tuple[str | int, ...]
    value: Any
    tolerance: float | None = None


@dataclass(frozen=True)
class ReplaySpec:
    case_id: str
    question: str
    expected_intent_types: tuple[str, ...]
    required_tools: tuple[str, ...] = ()
    required_tool_args: tuple[RequiredToolArgs, ...] = ()
    required_tool_result_fields: tuple[RequiredToolResultField, ...] = ()
    required_bound_tools: tuple[str, ...] = ()
    required_trace_kinds: tuple[str, ...] = ()
    required_text: tuple[str, ...] = ()
    required_numbers: tuple[float, ...] = ()
    number_tolerance: float = 0.05
    expected_stop_reason: str = "final_answer"
    require_structured_tool_results: bool = False


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class SummaryRow:
    case_id: str
    ok: bool
    kind: str
    intent_types: tuple[str, ...]
    tools: tuple[str, ...]
    failed_checks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayTurnSpec:
    turn_id: str
    question: str
    expected_intent_types: tuple[str, ...]
    required_tools: tuple[str, ...] = ()
    required_tool_args: tuple[RequiredToolArgs, ...] = ()
    required_tool_result_fields: tuple[RequiredToolResultField, ...] = ()
    required_bound_tools: tuple[str, ...] = ()
    required_trace_kinds: tuple[str, ...] = ()
    required_text: tuple[str, ...] = ()
    required_numbers: tuple[float, ...] = ()
    number_tolerance: float = 0.05
    expected_stop_reason: str = "final_answer"
    require_structured_tool_results: bool = False
    require_prior_answer_verdict: bool = False
    required_prior_answer_verdict_text: tuple[str, ...] = ()
    required_prior_answer_verdict_numbers: tuple[float, ...] = ()
    deferred_assertions: tuple[str, ...] = ()


@dataclass(frozen=True)
class MultiTurnReplaySpec:
    transcript_id: str
    title: str
    turns: tuple[ReplayTurnSpec, ...]
    notes: tuple[str, ...] = ()


def build_replay_specs() -> dict[str, ReplaySpec]:
    return {
        "D1": ReplaySpec(
            case_id="D1",
            question="Which plant is offline and what is the associated open alert?",
            expected_intent_types=("A",),
            required_text=("tamil", "grid_disconnection"),
            required_numbers=(1.0,),
        ),
        "D2": ReplaySpec(
            case_id="D2",
            question="What was the average daily yield of Rajasthan Solar Park last week?",
            expected_intent_types=("B",),
            required_tool_args=(
                RequiredToolArgs(tool="daily_yield", args={"plant": "4135001", "window": "last_week"}),
            ),
            required_tool_result_fields=(
                RequiredToolResultField(tool="daily_yield", path=("window",), value="last_week"),
                RequiredToolResultField(tool="daily_yield", path=("results", 0, "plant_id"), value="4135001"),
                RequiredToolResultField(tool="daily_yield", path=("results", 0, "avg_daily_yield"), value=123354.2),
                RequiredToolResultField(tool="daily_yield", path=("results", 0, "days"), value=7),
            ),
            required_text=("rajasthan",),
            required_numbers=(123354.2,),
        ),
        "D3": ReplaySpec(
            case_id="D3",
            question="Which inverters have open hotspot anomalies caused by soiling?",
            expected_intent_types=("C",),
            required_tools=("anomalies",),
            required_tool_args=(
                RequiredToolArgs(
                    tool="anomalies",
                    args={"status": "open", "anomaly_type": "hotspot", "cause": "soiling"},
                ),
            ),
            required_tool_result_fields=(
                RequiredToolResultField(tool="anomalies", path=("matched",), value=2),
                RequiredToolResultField(tool="anomalies", path=("status_counts", "open"), value=2),
                RequiredToolResultField(tool="anomalies", path=("anomaly_ids",), value=[7, 55]),
            ),
            required_text=("hotspot", "soiling"),
            required_numbers=(2.0, 7.0, 55.0),
        ),
        "D4": ReplaySpec(
            case_id="D4",
            question="What is the mean time to resolve a critical alert?",
            expected_intent_types=("B",),
            required_numbers=(6.3, 6.0),
        ),
        "D5": ReplaySpec(
            case_id="D5",
            question="What's the weather like at the Gujarat plant today?",
            expected_intent_types=("A", "B"),
            required_tools=("weather_readings",),
            required_tool_args=(
                RequiredToolArgs(tool="weather_readings", args={"plant": "4136001", "window": "today"}),
            ),
            required_tool_result_fields=(
                RequiredToolResultField(tool="weather_readings", path=("window",), value="today"),
                RequiredToolResultField(tool="weather_readings", path=("latest_reading", "plant_id"), value="4136001"),
                RequiredToolResultField(tool="weather_readings", path=("latest_reading", "ambient_temp"), value=26.04),
                RequiredToolResultField(tool="weather_readings", path=("latest_reading", "module_temp"), value=46.24),
                RequiredToolResultField(tool="weather_readings", path=("latest_reading", "irradiation"), value=799.34),
            ),
            required_text=("gujarat",),
            required_numbers=(26.04, 46.24, 799.34),
        ),
        "D6": ReplaySpec(
            case_id="D6",
            question="How much revenue did we lose from Tamil Nadu's downtime this month?",
            expected_intent_types=(),
            required_text=("can't answer", "dataset"),
            expected_stop_reason="out_of_scope",
        ),
        "A1": ReplaySpec(
            case_id="A1",
            question="Which plants are currently offline?",
            expected_intent_types=("A",),
            required_text=("tamil", "offline"),
        ),
        "A2": ReplaySpec(
            case_id="A2",
            question="How many inverters are in fault right now?",
            expected_intent_types=("A",),
            required_text=("fault",),
            required_numbers=(1.0,),
        ),
        "A3": ReplaySpec(
            case_id="A3",
            question="What open critical alerts exist?",
            expected_intent_types=("A",),
            required_text=("critical", "open"),
            required_numbers=(1.0,),
        ),
        "B1": ReplaySpec(
            case_id="B1",
            question="What is the average daily yield per plant over the last week?",
            expected_intent_types=("B",),
            required_text=("rajasthan", "gujarat", "tamil"),
            required_numbers=(123354.2, 68649.9, 151152.5),
        ),
        "B2": ReplaySpec(
            case_id="B2",
            question="Which inverter has the highest performance ratio?",
            expected_intent_types=("B",),
            required_text=("inv_4137001_04",),
            required_numbers=(0.9519,),
        ),
        "B3": ReplaySpec(
            case_id="B3",
            question="What is the mean time to resolve an alert?",
            expected_intent_types=("B",),
            required_numbers=(22.16, 25.0),
        ),
        "C1": ReplaySpec(
            case_id="C1",
            question="Which inverters have open hotspot anomalies?",
            expected_intent_types=("C",),
            required_tools=("anomalies",),
            required_text=("hotspot",),
            required_numbers=(7.0,),
        ),
        "C2": ReplaySpec(
            case_id="C2",
            question="What anomalies are caused by soiling?",
            expected_intent_types=("C",),
            required_tools=("anomalies",),
            required_text=("soiling",),
            required_numbers=(8.0,),
        ),
        "C3": ReplaySpec(
            case_id="C3",
            question="Summarise all unresolved anomalies for Rajasthan Solar Park.",
            expected_intent_types=("C",),
            required_tools=("anomalies",),
            required_tool_args=(
                RequiredToolArgs(tool="anomalies", args={"plant": "4135001", "status": "unresolved"}),
            ),
            required_tool_result_fields=(
                RequiredToolResultField(tool="anomalies", path=("matched",), value=15),
                RequiredToolResultField(tool="anomalies", path=("status_counts", "open"), value=7),
                RequiredToolResultField(tool="anomalies", path=("status_counts", "scheduled_repair"), value=5),
                RequiredToolResultField(tool="anomalies", path=("status_counts", "monitoring"), value=3),
            ),
            required_bound_tools=("anomalies", "inverters", "plants"),
            required_text=("rajasthan",),
            required_numbers=(15.0, 7.0, 5.0, 3.0),
            require_structured_tool_results=True,
        ),
        "P2": ReplaySpec(
            case_id="P2",
            question="List all plants and their status.",
            expected_intent_types=("A",),
            required_text=("rajasthan", "gujarat", "tamil", "active", "maintenance", "offline"),
        ),
        "P3": ReplaySpec(
            case_id="P3",
            question="What is the nameplate capacity of the Gujarat plant?",
            expected_intent_types=("A",),
            required_text=("gujarat",),
            required_numbers=(18.5,),
        ),
        "P4": ReplaySpec(
            case_id="P4",
            question="Which plant has the highest feed-in tariff?",
            expected_intent_types=("B",),
            required_bound_tools=("inverters", "plants"),
            required_text=("rajasthan",),
            required_numbers=(0.052,),
        ),
        "P5": ReplaySpec(
            case_id="P5",
            question="How many inverters does Rajasthan have?",
            expected_intent_types=("A",),
            required_text=("rajasthan",),
            required_numbers=(10.0,),
        ),
        "I2": ReplaySpec(
            case_id="I2",
            question="How many inverters are offline?",
            expected_intent_types=("A",),
            required_numbers=(15.0,),
        ),
        "I3": ReplaySpec(
            case_id="I3",
            question="Which inverters at Tamil Nadu are not online?",
            expected_intent_types=("A",),
            required_text=("tamil", "offline"),
            required_numbers=(12.0,),
        ),
        "I4": ReplaySpec(
            case_id="I4",
            question="Which inverters are silently not reporting (offline by data, not just status)?",
            expected_intent_types=("A",),
            required_text=("silent",),
            required_numbers=(16.0,),
        ),
        "I5": ReplaySpec(
            case_id="I5",
            question='Show inverters that are "online" in status but have an open alert.',
            expected_intent_types=("A",),
            required_text=("inv_4135001_05",),
            required_numbers=(4.0,),
        ),
        "G2": ReplaySpec(
            case_id="G2",
            question="Total energy generated by Rajasthan this month.",
            expected_intent_types=("B",),
            required_text=("rajasthan",),
            required_numbers=(3004224.3,),
        ),
        "G3": ReplaySpec(
            case_id="G3",
            question="Average AC power for INV_4135001_01 last 7 days.",
            expected_intent_types=("B",),
            required_text=("inv_4135001_01",),
            required_numbers=(593.10,),
        ),
        "G4": ReplaySpec(
            case_id="G4",
            question="Which inverter tops the fleet on performance ratio?",
            expected_intent_types=("B",),
            required_text=("inv_4137001_04",),
            required_numbers=(0.9519,),
        ),
        "G5": ReplaySpec(
            case_id="G5",
            question="What was the peak AC power across the fleet this month?",
            expected_intent_types=("B",),
            required_text=("inv_4135001_03",),
            required_numbers=(2505.92,),
        ),
        "G6": ReplaySpec(
            case_id="G6",
            question="Average performance ratio at night.",
            expected_intent_types=("B",),
            required_text=("undefined",),
        ),
        "W1": ReplaySpec(
            case_id="W1",
            question="Give me today's weather snapshot for the Gujarat site.",
            expected_intent_types=("A",),
            required_tools=("weather_readings",),
            required_tool_args=(
                RequiredToolArgs(tool="weather_readings", args={"plant": "4136001", "window": "today"}),
            ),
            required_tool_result_fields=(
                RequiredToolResultField(tool="weather_readings", path=("window",), value="today"),
                RequiredToolResultField(tool="weather_readings", path=("latest_reading", "plant_id"), value="4136001"),
                RequiredToolResultField(tool="weather_readings", path=("latest_reading", "ambient_temp"), value=26.04),
                RequiredToolResultField(tool="weather_readings", path=("latest_reading", "module_temp"), value=46.24),
                RequiredToolResultField(tool="weather_readings", path=("latest_reading", "irradiation"), value=799.34),
            ),
            required_text=("gujarat",),
            required_numbers=(26.04, 46.24, 799.34),
        ),
        "W2": ReplaySpec(
            case_id="W2",
            question="Average irradiation at Rajasthan last week.",
            expected_intent_types=("B",),
            required_text=("rajasthan",),
            required_numbers=(253.60,),
        ),
        "W3": ReplaySpec(
            case_id="W3",
            question="Which plant had the highest cloud cover this month?",
            expected_intent_types=("B",),
            required_text=("rajasthan",),
            required_numbers=(23.66,),
        ),
        "W4": ReplaySpec(
            case_id="W4",
            question="Was there any rainfall at Tamil Nadu this week?",
            expected_intent_types=("A", "B"),
            required_text=("no", "0.0"),
        ),
        "AL2": ReplaySpec(
            case_id="AL2",
            question="How many alerts are currently open?",
            expected_intent_types=("A",),
            required_numbers=(4.0,),
        ),
        "AL3": ReplaySpec(
            case_id="AL3",
            question="Show all alerts for Rajasthan.",
            expected_intent_types=("A",),
            required_text=("rajasthan",),
            required_numbers=(15.0, 13.0, 2.0),
        ),
        "AL4": ReplaySpec(
            case_id="AL4",
            question="What is the total downtime caused by resolved alerts?",
            expected_intent_types=("B",),
            required_numbers=(31836.0,),
        ),
        "AL5": ReplaySpec(
            case_id="AL5",
            question="Mean time to resolve an alert, all severities.",
            expected_intent_types=("B",),
            required_numbers=(22.16, 25.0),
        ),
        "AL6": ReplaySpec(
            case_id="AL6",
            question="What is the MTTR for open alerts?",
            expected_intent_types=("B",),
            required_text=("no inputs", "resolved_at"),
        ),
        "M1": ReplaySpec(
            case_id="M1",
            question="What maintenance is in progress?",
            expected_intent_types=("A",),
            required_numbers=(4.0,),
        ),
        "M2": ReplaySpec(
            case_id="M2",
            question="What maintenance is scheduled?",
            expected_intent_types=("A",),
            required_numbers=(3.0,),
        ),
        "M3": ReplaySpec(
            case_id="M3",
            question="Total maintenance cost on done tickets.",
            expected_intent_types=("B",),
            required_numbers=(41715.0,),
        ),
        "M4": ReplaySpec(
            case_id="M4",
            question="Average duration of completed maintenance.",
            expected_intent_types=("B",),
            required_numbers=(4.93, 12.0),
        ),
        "M5": ReplaySpec(
            case_id="M5",
            question="Which inverters at Gujarat have maintenance in progress?",
            expected_intent_types=("A",),
            required_text=("inv_4136001_06", "inv_4136001_07", "inv_4136001_08"),
            required_numbers=(3.0,),
        ),
        "AN3": ReplaySpec(
            case_id="AN3",
            question="How many open anomalies are there fleet-wide?",
            expected_intent_types=("C",),
            required_numbers=(28.0,),
        ),
        "AN4": ReplaySpec(
            case_id="AN4",
            question="Total estimated power loss from open anomalies.",
            expected_intent_types=("B", "C"),
            required_numbers=(1421.42,),
        ),
        "AN5": ReplaySpec(
            case_id="AN5",
            question="List critical anomalies and their recommended action.",
            expected_intent_types=("C",),
            required_text=("recommended",),
            required_numbers=(18.0,),
        ),
        "AN6": ReplaySpec(
            case_id="AN6",
            question="Give me a rundown of every unresolved anomaly at Rajasthan Solar Park.",
            expected_intent_types=("C",),
            required_tools=("anomalies",),
            required_tool_args=(
                RequiredToolArgs(tool="anomalies", args={"plant": "4135001", "status": "unresolved"}),
            ),
            required_tool_result_fields=(
                RequiredToolResultField(tool="anomalies", path=("matched",), value=15),
                RequiredToolResultField(tool="anomalies", path=("status_counts", "open"), value=7),
                RequiredToolResultField(tool="anomalies", path=("status_counts", "scheduled_repair"), value=5),
                RequiredToolResultField(tool="anomalies", path=("status_counts", "monitoring"), value=3),
            ),
            required_bound_tools=("anomalies", "inverters", "plants"),
            required_trace_kinds=("intent_finished", "synthesis_started", "model_invoke_started"),
            required_text=("rajasthan",),
            required_numbers=(15.0, 7.0, 5.0, 3.0),
            require_structured_tool_results=True,
        ),
        "AN7": ReplaySpec(
            case_id="AN7",
            question="Which anomalies are linked to a maintenance ticket?",
            expected_intent_types=("C",),
            required_numbers=(2.0, 1.0, 4.0, 6.0, 5.0),
        ),
        "X1": ReplaySpec(
            case_id="X1",
            question="Give me a full health summary of the Gujarat plant.",
            expected_intent_types=("A", "B", "C"),
            required_text=("gujarat",),
            required_numbers=(5.0, 3.0, 0.0, 1.0, 8.0, 3.0),
        ),
        "X2": ReplaySpec(
            case_id="X2",
            question="Compare Rajasthan and Tamil Nadu on open anomalies and yield.",
            expected_intent_types=("B", "C"),
            required_text=("rajasthan", "tamil"),
            required_numbers=(7.0, 13.0, 123354.2, 151152.5),
        ),
        "X3": ReplaySpec(
            case_id="X3",
            question="For the inverter in fault, what alert and anomalies does it have?",
            expected_intent_types=("A", "C"),
            required_text=("inv_4135001_10",),
            required_numbers=(2.0, 16.0, 27.0, 4.0, 17.0, 54.0),
        ),
        "X4": ReplaySpec(
            case_id="X4",
            question="Which plant is performing worst right now?",
            expected_intent_types=("B",),
            required_bound_tools=("performance_ratio", "inverters", "plants"),
            required_text=("rajasthan",),
            required_numbers=(0.9077,),
        ),
        "X5": ReplaySpec(
            case_id="X5",
            question="Forecast next week's generation for Rajasthan.",
            expected_intent_types=(),
            required_text=("can't answer", "historical"),
            expected_stop_reason="out_of_scope",
        ),
        "X6": ReplaySpec(
            case_id="X6",
            question="How is the plant doing?",
            expected_intent_types=(),
            required_text=("which plant",),
        ),
        "X7": ReplaySpec(
            case_id="X7",
            question="What's the status of plant 9999?",
            expected_intent_types=("A",),
            required_text=("no such plant",),
        ),
    }


def gate_case_ids(gate: str) -> tuple[str, ...]:
    if gate == "gate1":
        return GATE1_CASE_IDS
    if gate == "gate2":
        return GATE2_CASE_IDS
    if gate == "gate2a":
        return GATE2A_CASE_IDS
    if gate == "gate2b":
        return GATE2B_CASE_IDS
    raise ValueError(f"unknown gate: {gate}")


def gate_transcript_ids(gate: str) -> tuple[str, ...]:
    if gate in ("gate2", "gate2b"):
        return GATE2_TRANSCRIPT_IDS
    return ()


def _truncate_cell(value: str, *, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return value[:max_len]
    return value[: max_len - 3] + "..."


def _format_table(rows: list[SummaryRow]) -> str:
    headers = ("Status", "Kind", "Case", "Intent", "Tools", "Failed Checks")
    rendered_rows: list[tuple[str, str, str, str, str, str]] = []
    for row in rows:
        rendered_rows.append(
            (
                "✓ PASS" if row.ok else "✗ FAIL",
                row.kind,
                row.case_id,
                ",".join(row.intent_types) or "-",
                _truncate_cell(",".join(row.tools) or "-", max_len=28),
                _truncate_cell(",".join(row.failed_checks) or "-", max_len=40),
            )
        )

    widths = [len(header) for header in headers]
    for rendered in rendered_rows:
        for index, cell in enumerate(rendered):
            widths[index] = max(widths[index], len(cell))

    def fmt_row(values: tuple[str, ...]) -> str:
        return "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(values)) + " |"

    separator = "|-" + "-|-".join("-" * width for width in widths) + "-|"
    lines = [fmt_row(headers), separator]
    lines.extend(fmt_row(rendered) for rendered in rendered_rows)
    return "\n".join(lines)


def print_summary_table(rows: list[SummaryRow]) -> None:
    if not rows:
        return
    passed = sum(1 for row in rows if row.ok)
    failed = len(rows) - passed
    print("\nSummary")
    print(_format_table(rows))
    print(f"\nTotals: {passed} passed, {failed} failed, {len(rows)} total")


def extract_numbers(text: str) -> list[float]:
    return [float(match.replace(",", "")) for match in re.findall(r"-?\d[\d,]*\.?\d*", text)]


def extract_numbers_from_value(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        return extract_numbers(value)
    if isinstance(value, dict):
        numbers: list[float] = []
        for nested in value.values():
            numbers.extend(extract_numbers_from_value(nested))
        return numbers
    if isinstance(value, (list, tuple)):
        numbers: list[float] = []
        for nested in value:
            numbers.extend(extract_numbers_from_value(nested))
        return numbers
    return []


def contains_subsequence(actual: list[str], required: tuple[str, ...]) -> bool:
    if not required:
        return True
    index = 0
    for item in actual:
        if item == required[index]:
            index += 1
            if index == len(required):
                return True
    return False


def _tool_arg_requirements(raw: Any) -> tuple[RequiredToolArgs, ...]:
    requirements: list[RequiredToolArgs] = []
    for item in raw or ():
        if not isinstance(item, dict):
            raise ValueError(f"required_tool_args entries must be objects, got {type(item).__name__}")
        args = item.get("args", {})
        if not isinstance(args, dict):
            raise ValueError("required_tool_args entries must define an object 'args'")
        requirements.append(RequiredToolArgs(tool=str(item["tool"]), args=dict(args)))
    return tuple(requirements)


def _tool_result_field_requirements(raw: Any) -> tuple[RequiredToolResultField, ...]:
    requirements: list[RequiredToolResultField] = []
    for item in raw or ():
        if not isinstance(item, dict):
            raise ValueError(f"required_tool_result_fields entries must be objects, got {type(item).__name__}")
        path = item.get("path", item.get("field"))
        if "value" in item:
            value = item["value"]
        elif "expected" in item:
            value = item["expected"]
        else:
            raise ValueError("required_tool_result_fields entries must define 'value' or 'expected'")
        tolerance = item.get("tolerance")
        requirements.append(
            RequiredToolResultField(
                tool=str(item["tool"]),
                path=_field_path(path),
                value=value,
                tolerance=float(tolerance) if tolerance is not None else None,
            )
        )
    return tuple(requirements)


def _field_path(raw: Any) -> tuple[str | int, ...]:
    if isinstance(raw, str):
        parts = raw.split(".") if raw else []
    elif isinstance(raw, (list, tuple)):
        parts = list(raw)
    else:
        raise ValueError("result field path must be a dot path or list")
    return tuple(_field_path_part(part) for part in parts)


def _field_path_part(part: Any) -> str | int:
    if isinstance(part, int) and not isinstance(part, bool):
        return part
    text = str(part)
    return int(text) if text.isdigit() else text


def replay_spec_from_mapping(case_id: str, payload: dict[str, Any]) -> ReplaySpec:
    return ReplaySpec(
        case_id=case_id,
        question=str(payload["question"]),
        expected_intent_types=tuple(str(value) for value in payload.get("expected_intent_types", ())),
        required_tools=tuple(str(value) for value in payload.get("required_tools", ())),
        required_tool_args=_tool_arg_requirements(payload.get("required_tool_args")),
        required_tool_result_fields=_tool_result_field_requirements(payload.get("required_tool_result_fields")),
        required_bound_tools=tuple(str(value) for value in payload.get("required_bound_tools", ())),
        required_trace_kinds=tuple(str(value) for value in payload.get("required_trace_kinds", ())),
        required_text=tuple(str(value) for value in payload.get("required_text", ())),
        required_numbers=tuple(float(value) for value in payload.get("required_numbers", ())),
        number_tolerance=float(payload.get("number_tolerance", 0.05)),
        expected_stop_reason=str(payload.get("expected_stop_reason", "final_answer")),
        require_structured_tool_results=bool(payload.get("require_structured_tool_results", False)),
    )


def multi_turn_fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "multi_turn"


def load_multi_turn_spec(path: str | Path) -> MultiTurnReplaySpec:
    fixture_path = Path(path)
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    transcript_id = str(raw["transcript_id"])
    title = str(raw["title"])
    turns_payload = raw.get("turns")
    if not isinstance(turns_payload, list) or not turns_payload:
        raise ValueError(f"{fixture_path} must define a non-empty turns list")
    turns: list[ReplayTurnSpec] = []
    for index, turn_payload in enumerate(turns_payload, start=1):
        spec = replay_spec_from_mapping(f"{transcript_id}:{index}", turn_payload)
        turns.append(
            ReplayTurnSpec(
                turn_id=str(turn_payload.get("turn_id", f"turn-{index}")),
                question=spec.question,
                expected_intent_types=spec.expected_intent_types,
                required_tools=spec.required_tools,
                required_tool_args=spec.required_tool_args,
                required_tool_result_fields=spec.required_tool_result_fields,
                required_bound_tools=spec.required_bound_tools,
                required_trace_kinds=spec.required_trace_kinds,
                required_text=spec.required_text,
                required_numbers=spec.required_numbers,
                number_tolerance=spec.number_tolerance,
                expected_stop_reason=spec.expected_stop_reason,
                require_structured_tool_results=spec.require_structured_tool_results,
                require_prior_answer_verdict=bool(turn_payload.get("require_prior_answer_verdict", False)),
                required_prior_answer_verdict_text=tuple(
                    str(value) for value in turn_payload.get("required_prior_answer_verdict_text", ())
                ),
                required_prior_answer_verdict_numbers=tuple(
                    float(value) for value in turn_payload.get("required_prior_answer_verdict_numbers", ())
                ),
                deferred_assertions=tuple(
                    str(value) for value in turn_payload.get("deferred_assertions", ())
                ),
            )
        )
    return MultiTurnReplaySpec(
        transcript_id=transcript_id,
        title=title,
        turns=tuple(turns),
        notes=tuple(str(value) for value in raw.get("notes", ())),
    )


def build_multi_turn_specs(fixtures_dir: str | Path | None = None) -> dict[str, MultiTurnReplaySpec]:
    root = Path(fixtures_dir) if fixtures_dir is not None else multi_turn_fixtures_dir()
    if not root.exists():
        return {}
    specs: dict[str, MultiTurnReplaySpec] = {}
    for path in sorted(root.glob("*.json")):
        spec = load_multi_turn_spec(path)
        specs[spec.transcript_id] = spec
    return specs


def _tool_call_matches_args(call: dict[str, Any], requirement: RequiredToolArgs, tolerance: float) -> bool:
    if str(call.get("name", "")) != requirement.tool:
        return False
    args = call.get("args")
    if not isinstance(args, dict):
        return False
    return _partial_value_matches(args, requirement.args, tolerance)


def _tool_result_field_matches(
    tool_calls: list[dict[str, Any]],
    requirement: RequiredToolResultField,
    default_tolerance: float,
) -> tuple[bool, list[Any]]:
    found_values: list[Any] = []
    tolerance = requirement.tolerance if requirement.tolerance is not None else default_tolerance
    for call in tool_calls:
        if str(call.get("name", "")) != requirement.tool:
            continue
        found, value = _value_at_path(call.get("result"), requirement.path)
        if not found:
            continue
        found_values.append(value)
        if _value_matches(value, requirement.value, tolerance):
            return True, found_values
    return False, found_values


def _value_at_path(value: Any, path: tuple[str | int, ...]) -> tuple[bool, Any]:
    current = value
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or part < 0 or part >= len(current):
                return False, None
            current = current[part]
            continue
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _partial_value_matches(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and _partial_value_matches(actual[key], value, tolerance)
            for key, value in expected.items()
        )
    return _value_matches(actual, expected, tolerance)


def _value_matches(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(expected, dict):
        return _partial_value_matches(actual, expected, tolerance)
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(
            _value_matches(actual_value, expected_value, tolerance)
            for actual_value, expected_value in zip(actual, expected)
        )
    expected_number = _as_number(expected)
    actual_number = _as_number(actual)
    if expected_number is not None and actual_number is not None:
        return abs(actual_number - expected_number) <= tolerance
    if isinstance(expected, str) or isinstance(actual, str):
        return str(actual).strip().lower() == str(expected).strip().lower()
    return actual == expected


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _format_path(path: tuple[str | int, ...]) -> str:
    return ".".join(str(part) for part in path)


def evaluate_payload(spec: ReplaySpec, payload: dict[str, Any]) -> list[CheckResult]:
    answer = str(payload.get("answer", ""))
    answer_lower = answer.lower()
    tool_calls = [call for call in payload.get("tool_calls", []) if isinstance(call, dict)]
    tool_names = [str(call.get("name", "")) for call in tool_calls]
    bound_tools = [str(name) for name in payload.get("bound_tools", [])]
    trace_kinds = [str(event.get("kind", "")) for event in payload.get("trace_events", [])]
    actual_types = tuple(str(v) for v in payload.get("intent", {}).get("types", []))
    actual_numbers = extract_numbers(answer)

    checks = [
        CheckResult(
            name="stop_reason",
            ok=str(payload.get("stop_reason", "")) == spec.expected_stop_reason,
            detail=f"expected {spec.expected_stop_reason}, got {payload.get('stop_reason', '')}",
        ),
        CheckResult(
            name="intent_types",
            ok=all(intent_type in actual_types for intent_type in spec.expected_intent_types),
            detail=f"expected at least {list(spec.expected_intent_types)}, got {list(actual_types)}",
        ),
        CheckResult(
            name="tool_chain",
            ok=contains_subsequence(tool_names, spec.required_tools),
            detail=f"expected subsequence {list(spec.required_tools)}, got {tool_names}",
        ),
        CheckResult(
            name="bound_tools",
            ok=contains_subsequence(bound_tools, spec.required_bound_tools),
            detail=f"expected subsequence {list(spec.required_bound_tools)}, got {bound_tools}",
        ),
        CheckResult(
            name="trace_kinds",
            ok=contains_subsequence(trace_kinds, spec.required_trace_kinds),
            detail=f"expected subsequence {list(spec.required_trace_kinds)}, got {trace_kinds}",
        ),
    ]
    if spec.require_structured_tool_results:
        malformed = [
            str(call.get("name", ""))
            for call in tool_calls
            if not isinstance(call.get("result"), dict) or "ok" not in call.get("result", {})
        ]
        checks.append(
            CheckResult(
                name="structured_tool_results",
                ok=not malformed,
                detail=f"non-structured tool results for {malformed}",
            )
        )
    for index, requirement in enumerate(spec.required_tool_args, start=1):
        matched = any(_tool_call_matches_args(call, requirement, spec.number_tolerance) for call in tool_calls)
        actual_args = [call.get("args", {}) for call in tool_calls if str(call.get("name", "")) == requirement.tool]
        checks.append(
            CheckResult(
                name=f"tool_args:{index}:{requirement.tool}",
                ok=matched,
                detail=f"expected {requirement.args}, got {actual_args}",
            )
        )
    for index, requirement in enumerate(spec.required_tool_result_fields, start=1):
        matched, found_values = _tool_result_field_matches(tool_calls, requirement, spec.number_tolerance)
        checks.append(
            CheckResult(
                name=f"tool_result:{index}:{requirement.tool}:{_format_path(requirement.path)}",
                ok=matched,
                detail=f"expected {requirement.value!r}, got {found_values}",
            )
        )
    for snippet in spec.required_text:
        checks.append(
            CheckResult(
                name=f"text:{snippet}",
                ok=snippet.lower() in answer_lower,
                detail=f"answer did not contain '{snippet}'",
            )
        )
    for number in spec.required_numbers:
        matched = any(abs(actual - number) <= spec.number_tolerance for actual in actual_numbers)
        checks.append(
            CheckResult(
                name=f"number:{number}",
                ok=matched,
                detail=f"answer numbers {actual_numbers} did not match {number}±{spec.number_tolerance}",
            )
        )
    return checks


def evaluate_turn_payload(spec: ReplayTurnSpec, payload: dict[str, Any]) -> list[CheckResult]:
    checks = evaluate_payload(
        ReplaySpec(
            case_id=spec.turn_id,
            question=spec.question,
            expected_intent_types=spec.expected_intent_types,
            required_tools=spec.required_tools,
            required_tool_args=spec.required_tool_args,
            required_tool_result_fields=spec.required_tool_result_fields,
            required_bound_tools=spec.required_bound_tools,
            required_trace_kinds=spec.required_trace_kinds,
            required_text=spec.required_text,
            required_numbers=spec.required_numbers,
            number_tolerance=spec.number_tolerance,
            expected_stop_reason=spec.expected_stop_reason,
            require_structured_tool_results=spec.require_structured_tool_results,
        ),
        payload,
    )
    verdict = payload.get("prior_answer_verdict")
    if spec.require_prior_answer_verdict:
        checks.append(
            CheckResult(
                name="prior_answer_verdict:present",
                ok=isinstance(verdict, dict),
                detail=f"expected structured prior_answer_verdict, got {type(verdict).__name__}",
            )
        )
    if isinstance(verdict, dict):
        verdict_text = json.dumps(verdict, sort_keys=True).lower()
        verdict_numbers = extract_numbers_from_value(verdict)
        for snippet in spec.required_prior_answer_verdict_text:
            checks.append(
                CheckResult(
                    name=f"prior_answer_verdict:text:{snippet}",
                    ok=snippet.lower() in verdict_text,
                    detail=f"prior_answer_verdict did not contain '{snippet}'",
                )
            )
        for number in spec.required_prior_answer_verdict_numbers:
            matched = any(abs(actual - number) <= spec.number_tolerance for actual in verdict_numbers)
            checks.append(
                CheckResult(
                    name=f"prior_answer_verdict:number:{number}",
                    ok=matched,
                    detail=(
                        f"prior_answer_verdict numbers {verdict_numbers} "
                        f"did not match {number}±{spec.number_tolerance}"
                    ),
                )
            )
    return checks


def _create_session(base_url: str, title: str) -> str:
    body = json.dumps({"title": title}).encode()
    req = request.Request(
        f"{base_url.rstrip('/')}/api/sessions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["id"]


def _post_question(base_url: str, *, session_id: str, question: str, gating_mode: str) -> dict[str, Any]:
    body = json.dumps({
        "question": question,
        "gating_mode": gating_mode,
        "session_id": session_id,
    }).encode()
    req = request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def run_case(base_url: str, spec: ReplaySpec, gating_mode: str = "gated") -> dict[str, Any]:
    session_id = _create_session(base_url, f"Replay {spec.case_id}")
    return _post_question(base_url, session_id=session_id, question=spec.question, gating_mode=gating_mode)


def run_multi_turn_case(
    base_url: str,
    spec: MultiTurnReplaySpec,
    gating_mode: str = "gated",
) -> list[tuple[ReplayTurnSpec, dict[str, Any]]]:
    session_id = _create_session(base_url, f"Replay {spec.transcript_id}")
    results: list[tuple[ReplayTurnSpec, dict[str, Any]]] = []
    for turn in spec.turns:
        payload = _post_question(
            base_url,
            session_id=session_id,
            question=turn.question,
            gating_mode=gating_mode,
        )
        results.append((turn, payload))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=".venv/bin/python -m app.case_replay",
        description="Replay oracle-backed cases through the chat API and validate intent/tool/answer checks.",
    )
    parser.add_argument("--server", default="http://127.0.0.1:9006", help="server base URL")
    parser.add_argument("--gating-mode", choices=["gated", "bind_all"], default="gated")
    parser.add_argument("--gate", choices=["gate1", "gate2", "gate2a", "gate2b"], action="append", default=[])
    parser.add_argument("--case", action="append", default=[], help="case id to replay; repeatable")
    parser.add_argument(
        "--transcript",
        action="append",
        default=[],
        help="multi-turn transcript id to replay; repeatable",
    )
    args = parser.parse_args(argv)

    build_oracle()  # validates the oracle can be built before replay
    specs = build_replay_specs()
    multi_turn_specs = build_multi_turn_specs()
    selected_ids: list[str] = []
    gate_transcripts: list[str] = []
    for gate in args.gate:
        selected_ids.extend(gate_case_ids(gate))
        gate_transcripts.extend(gate_transcript_ids(gate))
    selected_ids.extend(args.case)
    if not selected_ids:
        selected_ids = list(specs)
    # Preserve order while removing duplicates across gate expansions / explicit cases.
    selected_ids = list(dict.fromkeys(selected_ids))
    summary_rows: list[SummaryRow] = []
    rc = 0
    for case_id in selected_ids:
        if case_id not in specs:
            print(f"{case_id}: unknown case id")
            rc = 1
            continue
        spec = specs[case_id]
        payload = run_case(args.server, spec, gating_mode=args.gating_mode)
        checks = evaluate_payload(spec, payload)
        ok = all(check.ok for check in checks)
        print(f"{case_id}: {'PASS' if ok else 'FAIL'}")
        print(f"  question: {spec.question}")
        print(f"  intent: {payload.get('intent', {}).get('types', [])}")
        print(f"  tools: {[call.get('name') for call in payload.get('tool_calls', [])]}")
        for check in checks:
            print(f"  - {check.name}: {'ok' if check.ok else 'fail'} ({check.detail})")
        summary_rows.append(
            SummaryRow(
                case_id=case_id,
                ok=ok,
                kind="case",
                intent_types=tuple(str(v) for v in payload.get("intent", {}).get("types", [])),
                tools=tuple(str(call.get("name", "")) for call in payload.get("tool_calls", [])),
                failed_checks=tuple(check.name for check in checks if not check.ok),
            )
        )
        if not ok:
            rc = 1
    selected_transcripts = list(dict.fromkeys(gate_transcripts + (args.transcript or [])))
    for transcript_id in selected_transcripts:
        if transcript_id not in multi_turn_specs:
            print(f"{transcript_id}: unknown transcript id")
            rc = 1
            continue
        transcript = multi_turn_specs[transcript_id]
        turn_results = run_multi_turn_case(args.server, transcript, gating_mode=args.gating_mode)
        transcript_ok = True
        print(f"{transcript.transcript_id}: {transcript.title}")
        for turn, payload in turn_results:
            checks = evaluate_turn_payload(turn, payload)
            ok = all(check.ok for check in checks)
            transcript_ok = transcript_ok and ok
            print(f"  {turn.turn_id}: {'PASS' if ok else 'FAIL'}")
            print(f"    question: {turn.question}")
            print(f"    intent: {payload.get('intent', {}).get('types', [])}")
            print(f"    tools: {[call.get('name') for call in payload.get('tool_calls', [])]}")
            if turn.deferred_assertions:
                print(f"    deferred_assertions: {list(turn.deferred_assertions)}")
            for check in checks:
                print(f"    - {check.name}: {'ok' if check.ok else 'fail'} ({check.detail})")
            summary_rows.append(
                SummaryRow(
                    case_id=f"{transcript.transcript_id}:{turn.turn_id}",
                    ok=ok,
                    kind="turn",
                    intent_types=tuple(str(v) for v in payload.get("intent", {}).get("types", [])),
                    tools=tuple(str(call.get("name", "")) for call in payload.get("tool_calls", [])),
                    failed_checks=tuple(check.name for check in checks if not check.ok),
                )
            )
        if not transcript_ok:
            rc = 1
    print_summary_table(summary_rows)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

from app.ai.intent_schema import coerce_intent
from app.pipeline import _normalize_tool_args_for_question, select_tool_names
from app.tools import build_registry


def test_intent_coercion_marks_health_summary_as_a_b_c():
    intent = coerce_intent(
        {
            "types": ["A"],
            "entities": {},
            "time_range": None,
            "metric": "",
            "out_of_scope": False,
            "confidence": 0.7,
            "summary": "Full health summary for Gujarat.",
        },
        question="Give me a full health summary of the Gujarat plant.",
    )

    assert intent["types"] == ["A", "B", "C"]


def test_intent_coercion_prefers_maintenance_duration_over_mttr():
    intent = coerce_intent(
        {
            "types": ["B"],
            "entities": {},
            "time_range": None,
            "metric": "",
            "out_of_scope": False,
            "confidence": 0.8,
            "summary": "",
        },
        question="What is the average duration of completed maintenance tickets?",
    )

    assert intent["metric"] == "maintenance_duration"
    assert intent["types"] == ["B"]


def test_intent_coercion_maps_done_ticket_cost_question_to_maintenance_cost():
    intent = coerce_intent(
        {
            "types": ["B"],
            "entities": {},
            "time_range": None,
            "metric": "",
            "out_of_scope": False,
            "confidence": 0.8,
            "summary": "",
        },
        question="Total maintenance cost on done tickets.",
    )

    assert intent["metric"] == "maintenance_cost"
    assert intent["types"] == ["B"]


def test_metric_specific_gating_binds_new_metric_tools():
    available = build_registry().names()

    assert select_tool_names(
        {"types": ["B"], "metric": "maintenance_cost", "summary": "Maintenance cost on done tickets"},
        gating_mode="gated",
        available_tools=available,
    ) == ["maintenance_cost", "inverters", "plants"]
    assert select_tool_names(
        {"types": ["B"], "metric": "ac_power", "summary": "Average AC power last week"},
        gating_mode="gated",
        available_tools=available,
    ) == ["ac_power", "inverters", "plants"]
    assert select_tool_names(
        {"types": ["B"], "metric": "power_loss", "summary": "Estimated power loss from open anomalies"},
        gating_mode="gated",
        available_tools=available,
    ) == ["anomalies", "inverters", "plants"]


def test_normalize_tool_args_for_first_metric_slice():
    assert _normalize_tool_args_for_question(
        name="alerts",
        args={},
        intent={"metric": "downtime"},
        question="What is the total downtime caused by resolved alerts?",
    ) == {"status": "resolved"}
    assert _normalize_tool_args_for_question(
        name="mttr",
        args={},
        intent={"metric": "mttr"},
        question="What is the MTTR for open alerts?",
    ) == {"status": "open"}
    assert _normalize_tool_args_for_question(
        name="maintenance_cost",
        args={},
        intent={"metric": "maintenance_cost"},
        question="Total maintenance cost on done tickets.",
    ) == {"status": "done"}
    assert _normalize_tool_args_for_question(
        name="maintenance_duration",
        args={},
        intent={"metric": "maintenance_duration"},
        question="Average duration of completed maintenance.",
    ) == {"status": "done"}

"""Tests for A1 (D3) fix: combined type+cause filter and matched_inverter_ids output."""
import pytest

from app.config import load_config
from app.data import PandasDataSource
from app.tools import ToolContext, build_registry


def _ctx() -> ToolContext:
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


def test_anomalies_combined_type_and_cause_returns_matched_inverter_ids():
    # D3: status=open + anomaly_type=hotspot + cause=soiling should return exactly 2 inverters
    registry = build_registry()
    result = registry.invoke(
        "anomalies",
        {"status": "open", "anomaly_type": "hotspot", "cause": "soiling"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["matched"] == 2
    assert sorted(result["anomaly_ids"]) == [7, 55]
    assert "matched_inverter_ids" in result
    assert sorted(result["matched_inverter_ids"]) == ["INV_4135001_09", "INV_4136001_08"]
    # summary also carries matched_inverter_ids
    assert "matched_inverter_ids" in result["summary"]
    assert sorted(result["summary"]["matched_inverter_ids"]) == ["INV_4135001_09", "INV_4136001_08"]


def test_anomalies_without_cause_filter_returns_all_open_hotspots():
    # Confirm that omitting cause does NOT return 2 — it returns 7 (all open hotspots)
    registry = build_registry()
    result = registry.invoke(
        "anomalies",
        {"status": "open", "anomaly_type": "hotspot"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["matched"] == 7


def test_anomalies_matched_inverter_ids_present_for_unfiltered_query():
    registry = build_registry()
    result = registry.invoke("anomalies", {}, _ctx())
    assert "matched_inverter_ids" in result
    assert isinstance(result["matched_inverter_ids"], list)


def test_anomalies_reports_total_estimated_power_loss_for_matched_frame():
    registry = build_registry()
    result = registry.invoke(
        "anomalies",
        {"status": "open", "anomaly_type": "hotspot", "cause": "soiling"},
        _ctx(),
    )

    assert result["matched"] == 2
    assert result["total_estimated_power_loss_kw"] == pytest.approx(0.087)
    assert result["summary"]["total_estimated_power_loss_kw"] == pytest.approx(0.087)


def test_anomalies_can_filter_for_linked_maintenance_tickets():
    registry = build_registry()
    result = registry.invoke("anomalies", {"linked_to_maintenance": True}, _ctx())

    assert result["ok"] is True
    assert result["matched"] == 2
    assert sorted(result["anomaly_ids"]) == [1, 4]
    assert result["total_estimated_power_loss_kw"] == pytest.approx(208.414)
    assert all(row["maintenance_ticket_id"] is not None for row in result["anomalies"])


def test_anomalies_can_filter_for_missing_maintenance_tickets():
    registry = build_registry()
    result = registry.invoke(
        "anomalies",
        {
            "status": "open",
            "anomaly_type": "hotspot",
            "cause": "soiling",
            "linked_to_maintenance": False,
        },
        _ctx(),
    )

    assert result["ok"] is True
    assert result["matched"] == 2
    assert sorted(result["anomaly_ids"]) == [7, 55]
    assert result["total_estimated_power_loss_kw"] == pytest.approx(0.087)
    assert all(row["maintenance_ticket_id"] is None for row in result["anomalies"])

import pandas as pd

from app.config import load_config
from app.data import PandasDataSource
from app.tools import ToolContext, build_registry
from app.tools.common import filter_exact


def _ctx() -> ToolContext:
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


def test_filter_exact_treats_wildcard_values_as_no_filter():
    frame = pd.DataFrame({"status": ["open", "closed"]})

    assert filter_exact(frame, "status", "*").equals(frame)
    assert filter_exact(frame, "status", "all").equals(frame)
    assert filter_exact(frame, "status", "").equals(frame)
    assert filter_exact(frame, "status", "   ").equals(frame)


def test_filter_exact_keeps_exact_matching_for_real_values():
    frame = pd.DataFrame({"status": ["open", "closed", "Open"], "ticket_id": [1, 2, 3]})

    filtered = filter_exact(frame, "status", "open")

    assert filtered["ticket_id"].tolist() == [1, 3]


def test_entity_tool_filters_ignore_wildcard_args():
    registry = build_registry()
    baseline = registry.invoke("alerts", {}, _ctx())
    wildcard = registry.invoke("alerts", {"status": "*", "severity": "all", "type": ""}, _ctx())

    assert baseline["ok"] is True
    assert wildcard["ok"] is True
    assert wildcard["matched"] == baseline["matched"]
    assert wildcard["alert_ids"] == baseline["alert_ids"]

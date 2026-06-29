import shutil

from datetime import datetime

from app.config import load_config
from app.data import TABLE_NAMES, PandasDataSource


def _source() -> PandasDataSource:
    return PandasDataSource(load_config().csv_dir)


def test_loads_all_seven_tables():
    source = _source()
    for name in TABLE_NAMES:
        frame = source.table(name)
        assert len(frame) > 0, f"{name} is empty"
    assert len(TABLE_NAMES) == 7


def test_unknown_table_raises():
    source = _source()
    try:
        source.table("does_not_exist")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_dataset_today_is_anchored_to_data_not_wallclock():
    source = _source()
    today = source.dataset_today()
    assert isinstance(today, datetime)
    # Dataset's last reading is ~2026-06-22 per the requirements.
    assert today.year == 2026 and today.month == 6


def test_table_returns_copy_not_cache():
    source = _source()
    frame = source.table("plants")
    frame.loc[:, "status"] = "MUTATED"
    assert (source.table("plants")["status"] != "MUTATED").all()


def test_rejects_parseable_dataset_with_missing_required_columns(tmp_path):
    config = load_config()
    dataset_dir = tmp_path / "dataset"
    shutil.copytree(config.csv_dir, dataset_dir)
    (dataset_dir / "plants.csv").write_text("plant_id\nP1\nP2\n", encoding="utf-8")

    try:
        PandasDataSource(dataset_dir)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == (
            "Dataset schema invalid for table 'plants': missing columns: "
            "name, location, region, latitude, longitude, capacity_mw, num_inverters, "
            "panel_type, tracker_type, commissioned_date, grid_operator, tariff_usd_per_kwh, status."
        )

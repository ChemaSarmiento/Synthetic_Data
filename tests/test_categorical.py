import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from synthetic_engine.calibration.categorical import profile_categories

SOURCE = dict(id="fixture", url="https://example.org", version="1", license="CC0", origin="synthetic_fixture")


def run(path, output, **kwargs):
    return profile_categories(path, output, ["kind"], "time", "%Y/%m/%d %H:%M", SOURCE, **kwargs)


def test_joint_calendar_and_invalid_accounting(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("kind,time\na,2022/09/01 10:00\na,2022/09/01 10:00\nb,2022/09/03 11:00\nb,bad\n,2022/09/03 11:00\n")
    result = run(path, tmp_path / "profile.json")
    assert result["audit"] == dict(rows=5, valid_rows=3, invalid_rows=2)
    assert result["joint_counts"] == [dict(values=["a", 3, 10], count=2), dict(values=["b", 5, 11], count=1)]
    assert result["weekday_mean_rows_per_calendar_day"][4] == 0
    assert result["weekday_exposure_days"] == {3: 1, 4: 1, 5: 1}
    assert result == run(path, tmp_path / "again.json")
    assert json.loads((tmp_path / "profile.json").read_text())["profile_sha256"] == result["profile_sha256"]
    with pytest.raises(FileExistsError):
        run(path, tmp_path / "profile.json")


def test_csv_parquet_semantics(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("kind,time\na,2022/09/01 10:00\nb,2022/09/02 11:00\n")
    parquet = tmp_path / "input.parquet"
    pq.write_table(pa.table(dict(kind=["a", "b"], time=["2022/09/01 10:00", "2022/09/02 11:00"])), parquet)
    a, b = run(csv, tmp_path / "a.json"), run(parquet, tmp_path / "b.json")
    for key in ("joint_counts", "audit", "marginals", "weekday_exposure_days"):
        assert a[key] == b[key]


def test_cardinality_and_empty_rejected(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("kind,time\na,2022/09/01 10:00\nb,2022/09/01 10:00\n")
    with pytest.raises(ValueError, match="cardinality"):
        run(path, tmp_path / "result.json", max_cells=1)
    assert not (tmp_path / "result.json").exists()
    path.write_text("kind,time\na,bad\n")
    with pytest.raises(ValueError, match="No valid"):
        run(path, tmp_path / "empty.json")

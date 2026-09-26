import json

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from synthetic_engine.config import Config
from synthetic_engine.domains.banking import BankingDomain
from synthetic_engine.engine import generate
from synthetic_engine.outputs.parquet import sha256, write_json
from synthetic_engine.checks import read
from synthetic_engine.validation import validate


def small(**kwargs):
    flat = {"domain": "banking_aml", "rows": 2400, "accounts": 100, "banks": 10, "days": 3, "batch_rows": 113,
            "laundering_fraction": 0.08, "legitimate_motif_fraction": 0.12} | kwargs
    return Config.from_dict(flat)



def event_tables(config):
    batches = list(BankingDomain(config).batches())
    return pa.concat_tables([b.events for b in batches]), pa.concat_tables([b.truth for b in batches])


def test_reproducible_across_output_batch_sizes():
    a, truth_a = event_tables(small())
    b, truth_b = event_tables(small(batch_rows=401))
    assert a.equals(b)
    assert truth_a.equals(truth_b)
    other, _ = event_tables(small(seed=42))
    assert not a.equals(other)


def test_complete_run_and_motif_controls(tmp_path):
    root = tmp_path / "dataset"
    manifest = generate(small(), root)
    report = validate(root)
    assert manifest["status"] == "complete"
    assert report["rows"] == 2400
    assert report["laundering_rows"] > 0
    for name in ("fan_in", "fan_out", "chain", "cycle"):
        assert report["scenario_counts"]["illicit_" + name] > 0
        assert report["scenario_counts"]["legitimate_" + name] > 0
    quantiles = report["amount_usd_quantiles"]
    assert quantiles["p99"] > quantiles["p50"] * 10
    features = json.loads((root / "model_features.json").read_text())["features"]
    assert not {"transaction_id", "scenario_id", "is_laundering", "scenario_motif"} & set(features)
    assert not json.loads((root / "evidence.json").read_text())["empirically_calibrated"]


def test_pre_event_history_is_independent_of_current_amount():
    domain = BankingDomain(small())
    features = domain._features(0, np.array([10_000_000, 20_000_000, 30_000_000]),
                                np.array([0, 1, 0]), np.array([1, 0, 2]), np.array([10., 30., 9000.]))
    assert features["sender_prior_out_count"].tolist() == [0, 0, 1]
    assert features["sender_prior_in_count"].tolist() == [0, 1, 1]
    assert features["sender_prior_mean_usd"].tolist() == [0., 0., 10.]
    assert features["sender_seconds_since_in"].tolist() == [-1., 10., 10.]


def test_residence_and_relationship_consistency():
    domain = BankingDomain(small(accounts=500))
    assert np.array_equal(domain.country, domain.customer_country[domain.owner])
    for group in np.unique(domain.customer_group):
        members = domain.customer_group == group
        assert len(set(domain.customer_country[members])) == 1
        assert len(set(domain.customer_business[members])) == 1
    tx, _ = event_tables(small(rows=10000, laundering_fraction=0.004, legitimate_motif_fraction=0.04))
    cross = tx["is_cross_border"].to_numpy()
    assert 0.03 < cross.mean() < 0.30


def test_refuses_overwrite(tmp_path):
    root = tmp_path / "existing"
    root.mkdir()
    sentinel = root / "keep.txt"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        generate(small(), root)
    assert sentinel.read_text() == "keep"


def test_detects_file_corruption(tmp_path):
    root = tmp_path / "run"
    generate(small(rows=100), root)
    path = next(root.glob("transactions/**/*.parquet"))
    with path.open("ab") as f:
        f.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        validate(root)


def test_replay_detects_leaked_history_even_with_updated_checksum(tmp_path):
    root = tmp_path / "run"
    generate(small(rows=100), root)
    manifest = json.loads((root / "manifest.json").read_text())
    entry = next(x for x in manifest["files"] if x["path"].startswith("transactions/"))
    path = root / entry["path"]
    table = read(path)
    index = table.schema.get_field_index("sender_prior_out_count")
    table = table.set_column(index, "sender_prior_out_count", pa.array([999] * table.num_rows, type=pa.int64()))
    pq.write_table(table, path)
    entry.update(bytes=path.stat().st_size, sha256=sha256(path))
    write_json(root / "manifest.json", manifest)
    with pytest.raises(ValueError, match="historical outgoing count"):
        validate(root)


@pytest.mark.parametrize("kwargs", [
    {"rows": -1}, {"rows": True}, {"days": 0}, {"accounts": 2}, {"batch_rows": 0},
    {"laundering_fraction": float("nan")}, {"start_date": "not-a-date"}, {"domain": "unknown"},
])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        BankingDomain(small(**kwargs))


def test_tiny_run_and_no_scenarios(tmp_path):
    root = tmp_path / "one"
    generate(small(rows=1), root)
    report = validate(root)
    assert report["rows"] == 1
    assert report["laundering_rows"] == 0


def test_daily_memory_guard():
    with pytest.raises(ValueError, match="max_day_rows"):
        BankingDomain(small(rows=200, days=2, batch_rows=100, max_day_rows=100))

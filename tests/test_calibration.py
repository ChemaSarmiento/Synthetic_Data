from dataclasses import replace
import json

import numpy as np
import pyarrow as pa
import pyarrow.csv as csv
import pyarrow.parquet as pq
import pytest

from synthetic_engine.calibration.histogram import FitConfig, compare, fit, holdout_mask, load_profile, sample
from synthetic_engine.config import Config
from synthetic_engine.domains.banking.calibration import AmountCalibration, BankingAmountModel
from synthetic_engine.engine import generate
from synthetic_engine.validation import validate


SOURCE = {"id": "fixture", "title": "Test fixture", "url": "urn:test:fixture",
          "version": "1", "license": "test-only", "origin": "synthetic_fixture"}


def config(**kwargs):
    return FitConfig(**({"source": SOURCE, "value_column": "amount", "group_column": "currency",
                         "unit": "payment_currency_major", "min_train": 10, "min_holdout": 5} | kwargs))


def fixture(path, count=2000):
    rng = np.random.default_rng(8)
    table = pa.table({"amount": rng.lognormal(5, 1.1, count),
                      "currency": np.where(np.arange(count) % 2, "USD", "EUR")})
    pq.write_table(table, path)
    return table


def test_profile_deterministic_across_batches_and_formats(tmp_path):
    source = tmp_path / "reference.parquet"
    table = fixture(source)
    first = fit(source, config(batch_rows=17), tmp_path / "first")
    second = fit(source, config(batch_rows=401), tmp_path / "second")
    assert first == second
    csv_path = tmp_path / "reference.csv"
    csv.write_csv(table, csv_path)
    third = fit(csv_path, config(batch_rows=39), tmp_path / "third")
    assert first["groups"] == third["groups"]
    assert first["holdout"] == third["holdout"]
    assert load_profile(tmp_path / "first/profile.json") == first


def test_holdout_never_changes_fitted_parameters(tmp_path):
    source = tmp_path / "source.parquet"
    table = fixture(source)
    c = config()
    first = fit(source, c, tmp_path / "fit-a")
    values = table["amount"].to_numpy().copy()
    values[holdout_mask(0, len(values), c.seed, c.holdout_fraction)] *= 1e8
    modified = tmp_path / "modified.parquet"
    pq.write_table(pa.table({"amount": values, "currency": table["currency"]}), modified)
    second = fit(modified, c, tmp_path / "fit-b")
    assert first["groups"] == second["groups"]
    assert all(d["outside_training_support_fraction"] == 1 for d in second["holdout"].values())


def test_generic_identity_transform_supports_negative_values(tmp_path):
    path = tmp_path / "telemetry.parquet"
    pq.write_table(pa.table({"temperature": np.linspace(-30, 30, 1000), "station": ["A"] * 1000}), path)
    profile = fit(path, config(value_column="temperature", group_column="station", unit="celsius", transform="identity"), tmp_path / "fit")
    assert profile["groups"]["A"]["minimum"] < 0
    values = sample(profile["groups"]["A"], 10000, np.random.default_rng(42), "identity")
    assert values.min() >= -30 and values.max() <= 30


def test_invalid_and_small_groups_are_reported(tmp_path):
    path = tmp_path / "invalid.parquet"
    pq.write_table(pa.table({"amount": [5.] * 100 + [0., -2., None, float("inf"), 2., 9.],
                            "currency": ["USD"] * 104 + [None, "tiny"]}), path)
    profile = fit(path, config(), tmp_path / "fit")
    assert profile["audit"]["invalid_rows"] == 5
    assert profile["groups"]["tiny"]["status"] == "insufficient_training"
    assert len(profile["groups"]["USD"]["edges"]) == 1
    report = compare(path, profile, "amount", "currency", {})
    assert report["unmatched_groups"] == {"tiny": 1}


def test_profile_tampering_detected(tmp_path):
    source = tmp_path / "ref.parquet"
    fixture(source)
    fit(source, config(), tmp_path / "fit")
    path = tmp_path / "fit/profile.json"
    profile = json.loads(path.read_text())
    profile["groups"]["USD"]["counts"][0] += 1
    path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="digest mismatch"):
        load_profile(path)


def test_reference_mutation_during_fit_is_rejected(tmp_path, monkeypatch):
    import synthetic_engine.calibration.histogram as module
    source = tmp_path / "ref.parquet"
    fixture(source)
    original = module.inventory
    calls = 0
    def changed(*args):
        nonlocal calls
        calls += 1
        result = original(*args)
        if calls == 2:
            result[0]["sha256"] = "changed"
        return result
    monkeypatch.setattr(module, "inventory", changed)
    with pytest.raises(ValueError, match="changed during"):
        fit(source, config(), tmp_path / "fit")
    assert not (tmp_path / "fit").exists()


def test_group_limit_and_no_overwrite(tmp_path):
    source = tmp_path / "ref.parquet"
    fixture(source)
    with pytest.raises(ValueError, match="cardinality"):
        fit(source, config(max_groups=1), tmp_path / "fit")
    fit(source, config(), tmp_path / "fit")
    with pytest.raises(FileExistsError):
        fit(source, config(), tmp_path / "fit")


def test_banking_uses_profile_and_validates_without_original_file(tmp_path):
    source = tmp_path / "reference.parquet"
    currencies = np.tile(["USD", "MXN", "GBP", "EUR", "BRL"], 400)
    pq.write_table(pa.table({"amount": np.full(len(currencies), 100.), "currency": currencies}), source)
    profile = fit(source, config(), tmp_path / "fit")
    path = tmp_path / "fit/profile.json"
    root = tmp_path / "generated"
    generate(Config(domain="banking", rows=1000, batch_rows=150, parameters={
        "accounts": 100, "banks": 10, "days": 3, "amount_calibration": {"profile": str(path)}}), root)
    for part in root.glob("transactions/**/*.parquet"):
        assert np.all(pq.ParquetFile(part).read()["amount_paid_minor"].to_numpy() == 10000)
    evidence = json.loads((root / "evidence.json").read_text())
    assert evidence["amount_calibration"]["reference_origin"] == "synthetic_fixture"
    assert evidence["empirically_calibrated"] is False
    report = compare(root / "transactions", profile, "amount_paid_minor", "payment_currency", {}, .01)
    assert all(g["bin_total_variation"] == 0 for g in report["groups"].values())
    path.unlink()
    assert validate(root)["passed"]


def test_missing_currency_requires_explicit_fallback(tmp_path):
    source = tmp_path / "ref.parquet"
    fixture(source)
    fit(source, config(), tmp_path / "fit")
    binding = AmountCalibration(str(tmp_path / "fit/profile.json"))
    with pytest.raises(ValueError, match="currencies"):
        BankingAmountModel(binding, ["USD", "MXN"])
    model = BankingAmountModel(replace(binding, missing_group="preset"), ["USD", "MXN"])
    assert model.fallbacks == ["MXN"]


@pytest.mark.parametrize("kwargs", [{"bins": 1}, {"batch_rows": 0}, {"seed": -1},
                                      {"holdout_fraction": float("nan")}, {"transform": "unknown"},
                                      {"source": {}}, {"min_train": 0}])
def test_bad_configuration(kwargs):
    with pytest.raises(ValueError):
        config(**kwargs)

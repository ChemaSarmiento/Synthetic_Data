"""Acceptance tests for ENG, BANK and AML specification boundaries."""

from dataclasses import fields
import json

import pyarrow as pa
import pytest

from synthetic_engine.config import Config
from synthetic_engine.core import Batch
from synthetic_engine.domains.banking.config import BankingConfig
from synthetic_engine.engine import generate
from synthetic_engine.outputs.parquet import ParquetOutput, safe_segment
from synthetic_engine.registry import DomainDefinition, get_domain, register
from synthetic_engine.validation import validate


class FixtureDomain:
    """Contract fixture only: not an evidence-backed production sensor model."""
    def __init__(self, config):
        self.config = config

    def dimensions(self):
        return {}

    def batches(self):
        for i in range(self.config.rows):
            yield Batch("sample", pa.table({"sample_id": [i], "temperature_c": [20.0 + i]}))

    def summaries(self):
        return {}

    def evidence(self):
        return {"profile_id": "test-fixture", "empirically_calibrated": False,
                "sources": [], "assumptions": ["Simple fixture to verify the domain contract"]}

    def model_features(self, schema):
        return {"features": ["temperature_c"], "excluded_identifiers": ["sample_id"], "target": None}


def test_non_banking_domain_uses_same_engine(tmp_path, monkeypatch):
    import synthetic_engine.registry as registry
    get_domain("banking")  # Load builtins before isolating this test registration.
    monkeypatch.setattr(registry, "_domains", dict(registry._domains))
    register(DomainDefinition("fixture_sensor", "0.1", "Test only", "test-spec",
                              FixtureDomain, lambda root, manifest: {"passed": True}))
    root = tmp_path / "sensor"
    manifest = generate(Config(domain="fixture_sensor", rows=3, batch_rows=1), root)
    assert manifest["layout"]["event_table"] == "records"
    assert not (root / "transactions").exists()
    assert not (root / "ground_truth").exists()
    assert validate(root)["domain"] == "fixture_sensor"
    metadata = json.loads((root / "model_features.json").read_text())
    assert metadata == {"features": ["temperature_c"], "excluded_identifiers": ["sample_id"], "target": None}


def test_shared_config_has_no_banking_fields():
    assert {f.name for f in fields(Config)} == {"domain", "seed", "rows", "batch_rows", "parameters"}


def test_banking_baseline_has_no_aml_truth(tmp_path):
    root = tmp_path / "baseline"
    generate(Config(domain="banking", rows=300, batch_rows=100,
                    parameters={"accounts": 100, "banks": 10, "days": 2}), root)
    assert not (root / "ground_truth").exists()
    assert validate(root)["scenario_counts"] == {}
    assert json.loads((root / "model_features.json").read_text())["target"] is None
    assert json.loads((root / "evidence.json").read_text())["active_scenarios"] == []


def test_legacy_configuration_maps_to_banking_scenario():
    config = Config.from_dict({"domain": "banking_aml", "rows": 300, "accounts": 100,
                               "banks": 10, "days": 2, "laundering_fraction": 0.04})
    assert config.domain == "banking"
    parameters = BankingConfig.from_run(config)
    assert parameters.aml.enabled
    assert parameters.aml.laundering_fraction == 0.04


@pytest.mark.parametrize("payload", [
    {"domain": "missing"}, {"domain": "banking", "accounts": 300},
    {"domain": "banking", "parameters": []}, {"domain": "banking_aml", "surprise": 1}, [],
])
def test_invalid_run_envelope(payload):
    with pytest.raises(ValueError):
        Config.from_dict(payload)


@pytest.mark.parametrize("parameters", [
    {"unknown": 1}, {"scenarios": {"fraud": {}}}, {"scenarios": []},
    {"scenarios": {"aml": {"enabled": "yes"}}}, {"scenarios": {"aml": 1}},
])
def test_invalid_domain_parameters(parameters):
    with pytest.raises(ValueError):
        BankingConfig.from_run(Config(domain="banking", parameters=parameters))


def test_unknown_domain_does_not_create_output(tmp_path):
    root = tmp_path / "unknown"
    with pytest.raises(ValueError, match="Unknown domain"):
        generate(Config(domain="missing"), root)
    assert not root.exists()


@pytest.mark.parametrize("segment", ["../escape", "/absolute", "", "a/b", ".."])
def test_unsafe_partition_names(segment):
    with pytest.raises(ValueError, match="Unsafe"):
        safe_segment(segment)


def test_output_adapter_rejects_escape(tmp_path):
    writer = ParquetOutput(tmp_path / "run")
    with pytest.raises(ValueError, match="Unsafe"):
        writer.write("../outside.parquet", pa.table({"x": [1]}))
    assert not (tmp_path / "outside.parquet").exists()


def test_failed_run_cannot_be_validated(tmp_path, monkeypatch):
    import synthetic_engine.registry as registry
    get_domain("banking")
    monkeypatch.setattr(registry, "_domains", dict(registry._domains))
    class BrokenDomain(FixtureDomain):
        def batches(self):
            yield Batch("sample", pa.table({"sample_id": [1], "temperature_c": [20.]}))
            raise ValueError("intentional fixture failure")
    register(DomainDefinition("fixture_failure", "0.1", "Test only", "test-spec",
                              BrokenDomain, lambda root, manifest: {"passed": True}))
    root = tmp_path / "failed"
    with pytest.raises(ValueError, match="intentional fixture failure"):
        generate(Config(domain="fixture_failure", rows=2), root)
    assert json.loads((root / "manifest.json").read_text())["status"] == "failed"
    with pytest.raises(ValueError, match="incomplete"):
        validate(root)


def test_schema_drift_is_rejected(tmp_path, monkeypatch):
    import synthetic_engine.registry as registry
    get_domain("banking")
    monkeypatch.setattr(registry, "_domains", dict(registry._domains))
    class DriftingDomain(FixtureDomain):
        def batches(self):
            yield Batch("sample", pa.table({"sample_id": [1], "temperature_c": [20.]}))
            yield Batch("sample", pa.table({"sample_id": [2], "unexpected": ["text"]}))
    register(DomainDefinition("fixture_drift", "0.1", "Test only", "test-spec",
                              DriftingDomain, lambda root, manifest: {"passed": True}))
    with pytest.raises(ValueError, match="schema changed"):
        generate(Config(domain="fixture_drift", rows=2), tmp_path / "drift")


def test_incomplete_evidence_fails_before_output(tmp_path, monkeypatch):
    import synthetic_engine.registry as registry
    get_domain("banking")
    monkeypatch.setattr(registry, "_domains", dict(registry._domains))
    class UndocumentedDomain(FixtureDomain):
        def evidence(self):
            return {"profile_id": "incomplete", "empirically_calibrated": False}
    register(DomainDefinition("fixture_no_sources", "0.1", "Test only", "test-spec",
                              UndocumentedDomain, lambda root, manifest: {"passed": True}))
    root = tmp_path / "undocumented"
    with pytest.raises(ValueError, match="sources and explicit assumptions"):
        generate(Config(domain="fixture_no_sources", rows=1), root)
    assert not root.exists()

from dataclasses import replace
import json

import pyarrow as pa
import pytest

from synthetic_engine.config import Config
from synthetic_engine.domains.banking.generator import BankingDomain
from synthetic_engine.domains.banking.payments import IBM_FORMATS, PAYMENT_FIELDS, normalize_ibm_formats, validate_preset_fields
from synthetic_engine.engine import generate
from synthetic_engine.validation import validate


def config(version=1):
    return Config(domain="banking", rows=300, batch_rows=100, parameters={
        "accounts": 40, "banks": 5, "days": 3, "payment_schema_version": version,
        "scenarios": {"aml": {"enabled": False}}})


def events(c):
    return pa.concat_tables([b.events for b in BankingDomain(c).batches()])


def test_opt_in_schema_preserves_every_existing_value():
    old, new = events(config()), events(config(2))
    assert new.select(old.column_names).equals(old)
    validate_preset_fields(old, 1)
    validate_preset_fields(new, 2)
    assert set(PAYMENT_FIELDS) <= set(new.column_names)
    assert set(new.column("payment_format").to_pylist()) <= {"wire", "card_unspecified", "bank_transfer_unspecified"}
    assert new.equals(events(replace(config(2), batch_rows=37)))


def test_reference_normalization_preserves_raw_semantics():
    source = pa.table({"Payment Format": list(IBM_FORMATS), "Amount Paid": ["1.23"] * 7})
    normalized = normalize_ibm_formats(source)
    assert normalized.select(source.column_names).equals(source)
    assert normalized.column("source_payment_format").to_pylist() == list(IBM_FORMATS)
    assert set(normalized.column("purpose").to_pylist()) == {"unspecified"}
    assert set(normalized.column("channel").to_pylist()) == {"unspecified"}
    rows = normalized.to_pylist()
    assert next(r for r in rows if r["Payment Format"] == "Reinvestment")["payment_rail"] == "unspecified"
    assert next(r for r in rows if r["Payment Format"] == "Bitcoin")["payment_asset_class"] == "crypto"
    with pytest.raises(ValueError, match="overwrite"):
        normalize_ibm_formats(normalized)
    with pytest.raises(ValueError, match="Unknown"):
        normalize_ibm_formats(pa.table({"Payment Format": ["new"]}))
    with pytest.raises(ValueError, match="Unknown"):
        normalize_ibm_formats(pa.table({"Payment Format": [None]}))


def test_v2_integrity_and_feature_exclusions(tmp_path):
    root = tmp_path / "run"
    generate(config(2), root)
    assert validate(root)["passed"]
    features = json.loads((root / "model_features.json").read_text())["features"]
    assert not {"source_payment_format", "payment_format_origin", "payment_mapping_status"} & set(features)
    table = events(config(2))
    bad = table.set_column(table.schema.get_field_index("payment_format"), "payment_format", pa.array(["ach"] * len(table)))
    with pytest.raises(ValueError, match="Inconsistent"):
        validate_preset_fields(bad, 2)
    with pytest.raises(ValueError, match="Incomplete"):
        validate_preset_fields(table.drop(["payment_format"]), 2)
    with pytest.raises(ValueError, match="v1"):
        validate_preset_fields(table, 1)


@pytest.mark.parametrize("version", [True, 0, 3, "2"])
def test_invalid_version(version):
    with pytest.raises(ValueError, match="payment_schema_version"):
        BankingDomain(config(version))

from dataclasses import replace

import numpy as np
import pyarrow as pa
import pytest

from synthetic_engine.config import Config
from synthetic_engine.domains.banking.generator import BankingDomain
from synthetic_engine.domains.banking.mechanisms import PaymentMechanisms, validate_mechanisms
from synthetic_engine.engine import generate
from synthetic_engine.validation import validate


def config(mechanisms=None, aml=False):
    return Config(domain="banking", rows=2000, batch_rows=113, parameters={
        "accounts": 100, "banks": 10, "days": 3, "payment_schema_version": 2,
        "payment_mechanisms": mechanisms or {}, "scenarios": {"aml": {"enabled": aml}}})


def tables(c):
    batches = list(BankingDomain(c).batches())
    return pa.concat_tables([b.events for b in batches]), (pa.concat_tables([b.truth for b in batches]) if batches[0].truth is not None else None)


@pytest.mark.parametrize("kind", ["cheque", "cash"])
def test_eligibility_accounting_and_independent_validation(tmp_path, kind):
    c = config({kind + "_probability": 1.0})
    tx, _ = tables(c)
    selected = np.array(tx.column("payment_rail")) == kind
    assert selected.sum() > 50
    validate_mechanisms(tx, PaymentMechanisms(**c.parameters["payment_mechanisms"]))
    # At probability one, every eligible row must be selected.
    purposes = ["purchase", "personal_transfer"] if kind == "cash" else ["supplier_payment", "salary", "personal_transfer"]
    data = tx.to_pydict()
    eligible = [(s == d and not own and purpose in purposes) for s,d,own,purpose in zip(
        data["sender_country"], data["receiver_country"], data["same_owner"], data["purpose"])]
    assert selected.tolist() == eligible
    fees = np.array(tx.column("fee_paid_minor")).copy()
    fees[np.flatnonzero(selected)[0]] = 1
    bad = tx.set_column(tx.schema.get_field_index("fee_paid_minor"), "fee_paid_minor", pa.array(fees))
    with pytest.raises(ValueError, match="accounting"):
        validate_mechanisms(bad, PaymentMechanisms(**c.parameters["payment_mechanisms"]))
    with pytest.raises(ValueError, match="Disabled"):
        validate_mechanisms(tx, PaymentMechanisms())
    root = tmp_path / kind
    generate(c, root)
    assert validate(root)["passed"]


def test_default_compatibility_and_aml_independence():
    c = config(aml=True)
    old, old_truth = tables(c)
    on = replace(c, parameters=c.parameters | {"payment_mechanisms": {"cheque_probability": .25, "cash_probability": .25}})
    new, new_truth = tables(on)
    altered = {"payment_rail", "channel", "fee_paid_minor", "payment_format"}
    preserved = [name for name in old.column_names if name not in altered]
    assert old.select(preserved).equals(new.select(preserved))
    assert old_truth.equals(new_truth)
    assert new.equals(tables(replace(on, batch_rows=71))[0])
    no_option = replace(c, parameters={k:v for k,v in c.parameters.items() if k != "payment_mechanisms"})
    assert old.equals(tables(no_option)[0])


@pytest.mark.parametrize("settings", [
    {"cash_probability": True}, {"cheque_probability": float("nan")},
    {"cash_probability": -1}, {"cheque_probability": 1.1},
    {"cash_probability": .6, "cheque_probability": .6},
])
def test_invalid_probabilities(settings):
    with pytest.raises(ValueError):
        PaymentMechanisms(**settings)


def test_mechanisms_require_v2():
    c = config({"cash_probability": .1})
    with pytest.raises(ValueError, match="require"):
        BankingDomain(replace(c, parameters=c.parameters | {"payment_schema_version": 1}))

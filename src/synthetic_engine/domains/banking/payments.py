"""Versioned payment semantics, independent of amount and entity simulation."""

import numpy as np
import pyarrow as pa

# Normalization is an explicit engineering interpretation, not fitted causality.
IBM_FORMATS = {
    "ACH": ("ach", "bank_transfer", "fiat", "coarsened"),
    "Credit Card": ("credit_card", "card", "fiat", "coarsened"),
    "Wire": ("wire", "wire", "fiat", "direct"),
    "Cheque": ("cheque", "cheque", "fiat", "direct"),
    "Cash": ("cash", "cash", "fiat", "direct"),
    "Reinvestment": ("reinvestment", "unspecified", "unspecified", "rail_unknown"),
    "Bitcoin": ("bitcoin", "crypto_transfer", "crypto", "direct"),
}
PAYMENT_FIELDS = ("payment_format", "source_payment_format", "payment_format_origin",
                  "payment_mapping_status", "payment_asset_class")
PRESET_FORMATS = {"bank_transfer": "bank_transfer_unspecified", "card": "card_unspecified", "wire": "wire"}
PRESET_FORMATS.update(cheque="cheque", cash="cash")


def preset_fields(rails):
    """Extend the old preset without extra RNG draws or invented reference subtypes."""
    if set(rails) - set(PRESET_FORMATS):
        raise ValueError("Unsupported preset rail")
    n = len(rails)
    return {
        "payment_format": [PRESET_FORMATS[r] for r in rails],
        "source_payment_format": ["not_applicable"] * n,
        "payment_format_origin": ["preset"] * n,
        "payment_mapping_status": ["preset"] * n,
        "payment_asset_class": ["fiat"] * n,
    }


def normalize_ibm_formats(table: pa.Table):
    """Preserve source fields; attach semantics without claiming executable events.

    Amounts, identities and timestamps remain source data, not engine transactions.
    In particular, this does not convert Bitcoin into fiat minor units.
    """
    additions = {*PAYMENT_FIELDS, "payment_rail", "purpose", "channel"}
    if additions & set(table.column_names):
        raise ValueError("Normalization would overwrite existing payment fields")
    raw = table.column("Payment Format").to_pylist()
    if any(value not in IBM_FORMATS for value in raw):
        raise ValueError("Unknown or missing IBM Payment Format")
    formats, rails, assets, statuses = zip(*(IBM_FORMATS[value] for value in raw)) if raw else ([], [], [], [])
    fields = dict(payment_format=formats, source_payment_format=raw,
                  payment_format_origin=["reference:ibm-amlworld"] * len(raw),
                  payment_mapping_status=statuses, payment_asset_class=assets,
                  payment_rail=rails, purpose=["unspecified"] * len(raw), channel=["unspecified"] * len(raw))
    for name, values in fields.items():
        table = table.append_column(name, pa.array(values, type=pa.string()))
    return table


def validate_preset_fields(table, version):
    present = set(PAYMENT_FIELDS) & set(table.column_names)
    if version == 1:
        if present:
            raise ValueError("Payment v1 must not contain v2 fields")
        return
    if version != 2 or present != set(PAYMENT_FIELDS):
        raise ValueError("Incomplete or unsupported payment schema")
    rails = table.column("payment_rail").to_numpy(zero_copy_only=False)
    expected = preset_fields(rails)
    for name, values in expected.items():
        if not np.array_equal(table.column(name).to_numpy(zero_copy_only=False), values):
            raise ValueError(f"Inconsistent preset payment field: {name}")

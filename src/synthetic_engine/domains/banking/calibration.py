"""Explicit binding from generic numeric profiles to banking background amounts."""

from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

from synthetic_engine.calibration.histogram import load_profile, sample


@dataclass(frozen=True)
class AmountCalibration:
    profile: str
    group_mapping: dict = field(default_factory=dict)
    missing_group: str = "error"

    def __post_init__(self):
        if not isinstance(self.profile, str) or not self.profile:
            raise ValueError("amount_calibration.profile must be a local file path")
        if self.missing_group not in {"error", "preset"}:
            raise ValueError("missing_group must be error or preset")
        if not isinstance(self.group_mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in self.group_mapping.items()):
            raise ValueError("group_mapping must map engine currencies to source currency names")


class BankingAmountModel:
    def __init__(self, binding: AmountCalibration, currencies):
        self.binding = binding
        self.profile = load_profile(Path(binding.profile))
        config = self.profile["fit_config"]
        if config["unit"] != "payment_currency_major" or config["transform"] != "log":
            raise ValueError("Banking amounts require log profiles in payment_currency_major units")
        self.mapping = {str(c): binding.group_mapping.get(str(c), str(c)) for c in currencies}
        self.covered = {c: group for c, group in self.mapping.items()
                        if self.profile["groups"].get(group, {}).get("status") == "fitted"}
        self.fallbacks = sorted(set(self.mapping) - set(self.covered))
        if self.fallbacks and binding.missing_group == "error":
            raise ValueError(f"No fitted reference group for currencies: {self.fallbacks}")
        if not self.covered:
            raise ValueError("No active engine currency has a fitted reference group")

    def apply(self, usd_amounts, currency_indices, currencies, fx, eligible, rng):
        for index, currency in enumerate(currencies):
            if currency not in self.covered:
                continue
            selected = eligible & (currency_indices == index)
            if selected.any():
                reference_group = self.covered[str(currency)]
                paid_major = sample(self.profile["groups"][reference_group], int(selected.sum()), rng, "log")
                usd_amounts[selected] = paid_major / fx[index]

    def evidence(self):
        return {
            "status": "partial_reference_fit",
            "scope": "background principal amounts conditional on payment currency, before currency rounding",
            "profile_sha256": self.profile["profile_sha256"],
            "reference_origin": self.profile["fit_config"]["source"]["origin"],
            "covered_currencies": self.covered,
            "preset_fallback_currencies": self.fallbacks,
            "profile": self.profile,
            "limitations": ["Country and currency mix is not fitted", "Account activity, timing, FX and labels remain assumed",
                            "Scenario amounts are not reference-fitted", "Does not fit customer-segment or network dependencies",
                            "Conditional amount calibration is not full-domain real-world validation"],
        }

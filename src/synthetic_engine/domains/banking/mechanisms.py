"""Optional, explicitly assumed cheque and cash-mediated transfer mechanisms."""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class PaymentMechanisms:
    cheque_probability: float = 0.0
    cash_probability: float = 0.0

    def __post_init__(self):
        for value in (self.cheque_probability, self.cash_probability):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Payment probabilities must be finite numbers between 0 and 1")
        if self.cheque_probability + self.cash_probability > 1:
            raise ValueError("Payment probabilities must sum to at most 1")

    @property
    def enabled(self):
        return self.cheque_probability > 0 or self.cash_probability > 0


def apply_mechanisms(config, rail, channel, purpose, country_src, country_dst, same_owner, seed, day):
    """Separate deterministic stream; never consult labels or alter amounts/accounts.

    Probabilities occupy disjoint intervals over all rows, then eligibility masks
    apply. Ineligible draws keep the original rail, rather than renormalizing.
    """
    if not config.enabled:
        return
    rng = np.random.default_rng(np.random.SeedSequence([seed, day, 7829]))
    draw = rng.random(len(rail))
    domestic = (country_src == country_dst) & ~same_owner
    cheque = domestic & np.isin(purpose, ["supplier_payment", "salary", "personal_transfer"])
    cash = domestic & np.isin(purpose, ["purchase", "personal_transfer"])
    cheque &= draw < config.cheque_probability
    cash &= (draw >= config.cheque_probability) & (draw < config.cheque_probability + config.cash_probability)
    rail[cheque], channel[cheque] = "cheque", "branch"
    rail[cash], channel[cash] = "cash", "in_person"


def validate_mechanisms(table, config):
    col = lambda name: table.column(name).to_numpy(zero_copy_only=False)
    rail, channel, purpose = col("payment_rail"), col("channel"), col("purpose")
    for kind, probability, expected_channel, purposes in (
        ("cheque", config.cheque_probability, "branch", ["supplier_payment", "salary", "personal_transfer"]),
        ("cash", config.cash_probability, "in_person", ["purchase", "personal_transfer"]),
    ):
        selected = rail == kind
        if not selected.any():
            continue
        if probability == 0:
            raise ValueError(f"Disabled payment mechanism: {kind}")
        valid = ((col("sender_country") == col("receiver_country")) &
                 (col("payment_currency") == col("receiving_currency")) &
                 ~col("same_owner") & (channel == expected_channel) & np.isin(purpose, purposes) &
                 (col("fx_rate") == 1) & (col("amount_paid_minor") == col("amount_received_minor")) &
                 (col("fee_paid_minor") == 0))
        if not np.all(valid[selected]):
            raise ValueError(f"Invalid {kind} mechanism eligibility or accounting")

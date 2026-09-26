"""Banking-only parameters, separate from the shared run envelope."""

from dataclasses import dataclass, field
from datetime import date

from synthetic_engine.config import Config
from synthetic_engine.domains.banking.scenarios.aml import AMLConfig
from synthetic_engine.domains.banking.calibration import AmountCalibration


@dataclass(frozen=True)
class BankingConfig:
    seed: int
    rows: int
    batch_rows: int
    accounts: int = 5_000
    banks: int = 30
    days: int = 30
    start_date: str = "2025-01-01"
    max_day_rows: int = 250_000
    aml: AMLConfig = field(default_factory=AMLConfig)
    amount_calibration: AmountCalibration | None = None
    payment_schema_version: int = 1

    def __post_init__(self):
        if type(self.payment_schema_version) is not int or self.payment_schema_version not in {1, 2}:
            raise ValueError("payment_schema_version must be 1 or 2")
        for key in ("accounts", "banks", "days", "max_day_rows"):
            if type(getattr(self, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if self.accounts < 20 or not 5 <= self.banks <= self.accounts or not 1 <= self.days <= 3660:
            raise ValueError("Require accounts >= 20, 5 <= banks <= accounts and 1 <= days <= 3660")
        if not 1 <= self.batch_rows <= self.max_day_rows <= 1_000_000:
            raise ValueError("Require 1 <= batch_rows <= max_day_rows <= 1,000,000")
        if self.rows > self.days * self.max_day_rows:
            raise ValueError("Too many rows: increase days; distributed generation is not implemented")
        date.fromisoformat(self.start_date)

    @classmethod
    def from_run(cls, config: Config):
        if config.domain != "banking":
            raise ValueError("BankingConfig requires the banking domain")
        parameters = dict(config.parameters)
        allowed = {"accounts", "banks", "days", "start_date", "max_day_rows", "scenarios", "amount_calibration", "payment_schema_version"}
        if parameters.keys() - allowed:
            raise ValueError(f"Unknown banking parameters: {sorted(parameters.keys() - allowed)}")
        scenarios = parameters.pop("scenarios", {})
        if not isinstance(scenarios, dict) or scenarios.keys() - {"aml"}:
            raise ValueError("Banking scenarios must be an object containing only the optional aml key")
        aml = scenarios.get("aml", {})
        if not isinstance(aml, dict):
            raise ValueError("aml must be a configuration object")
        calibration = parameters.pop("amount_calibration", None)
        if calibration is not None and not isinstance(calibration, dict):
            raise ValueError("amount_calibration must be a configuration object")
        binding = AmountCalibration(**calibration) if calibration is not None else None
        return cls(seed=config.seed, rows=config.rows, batch_rows=config.batch_rows,
                   aml=AMLConfig(**aml), amount_calibration=binding, **parameters)


def migrate_legacy(payload: dict):
    """Normalize v0.1 flat banking_aml configs; leave stored datasets untouched."""
    allowed = {"domain", "seed", "rows", "batch_rows", "accounts", "banks", "days", "start_date", "max_day_rows", "laundering_fraction", "legitimate_motif_fraction"}
    if payload.keys() - allowed:
        raise ValueError(f"Unknown legacy parameters: {sorted(payload.keys() - allowed)}")
    shared = {key: value for key, value in payload.items() if key in {"seed", "rows", "batch_rows"}}
    parameters = {key: value for key, value in payload.items() if key in {"accounts", "banks", "days", "start_date", "max_day_rows"}}
    aml = {key: value for key, value in payload.items() if key in {"laundering_fraction", "legitimate_motif_fraction"}}
    parameters["scenarios"] = {"aml": {"enabled": True, **aml}}
    return {"domain": "banking", **shared, "parameters": parameters}

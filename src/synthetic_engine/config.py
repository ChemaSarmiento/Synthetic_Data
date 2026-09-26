"""Strict, serializable run configuration. Unknown keys are rejected."""

from dataclasses import asdict, dataclass
from datetime import date
import json
from pathlib import Path


@dataclass(frozen=True)
class Config:
    domain: str = "banking_aml"
    seed: int = 20260926
    rows: int = 100_000
    accounts: int = 5_000
    banks: int = 30
    days: int = 30
    start_date: str = "2025-01-01"
    batch_rows: int = 10_000
    max_day_rows: int = 250_000
    laundering_fraction: float = 0.001
    legitimate_motif_fraction: float = 0.04

    def __post_init__(self):
        if self.domain != "banking_aml":
            raise ValueError("Only banking_aml is implemented in v0.1")
        for key in ("seed", "rows", "accounts", "banks", "days", "batch_rows", "max_day_rows"):
            if type(getattr(self, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if self.seed < 0 or self.rows < 1 or self.accounts < 20 or self.banks < 5:
            raise ValueError("Require seed >= 0, rows >= 1, accounts >= 20, banks >= 5")
        if self.banks > self.accounts or not 1 <= self.days <= 3660:
            raise ValueError("Require banks <= accounts and 1 <= days <= 3660")
        if not 1 <= self.batch_rows <= self.max_day_rows <= 1_000_000:
            raise ValueError("Require 1 <= batch_rows <= max_day_rows <= 1,000,000")
        if self.rows > self.days * self.max_day_rows:
            raise ValueError("Too many rows: increase days; distributed generation is not implemented")
        for key in ("laundering_fraction", "legitimate_motif_fraction"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 0.2:
                raise ValueError(f"{key} must be between 0 and 0.2")
        date.fromisoformat(self.start_date)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def load(cls, path: Path):
        return cls(**json.loads(path.read_text()))

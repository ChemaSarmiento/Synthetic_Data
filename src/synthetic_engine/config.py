"""Run-level configuration. Domains own and validate their parameters."""

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Config:
    domain: str
    seed: int = 20260926
    rows: int = 100_000
    batch_rows: int = 10_000
    parameters: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.domain, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", self.domain):
            raise ValueError("domain must be a lowercase registered identifier")
        for key in ("seed", "rows", "batch_rows"):
            if type(getattr(self, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if self.seed < 0 or self.rows < 1 or self.batch_rows < 1:
            raise ValueError("Require seed >= 0, rows >= 1 and batch_rows >= 1")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be an object")
        json.dumps(self.parameters, allow_nan=False)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, payload):
        from synthetic_engine.registry import get_domain, normalize_config
        normalized = normalize_config(payload)
        get_domain(normalized["domain"])
        try:
            return cls(**normalized)
        except TypeError as exc:
            raise ValueError(f"Invalid run configuration: {exc}") from exc

    @classmethod
    def load(cls, path: Path):
        return cls.from_dict(json.loads(path.read_text()))

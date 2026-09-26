"""Domain contract independent of banking or any particular output adapter."""

from dataclasses import dataclass
from typing import Iterator, Protocol
import pyarrow as pa


@dataclass
class Batch:
    partition: str
    events: pa.Table
    truth: pa.Table | None = None


class Domain(Protocol):
    def dimensions(self) -> dict[str, pa.Table]: ...
    def batches(self) -> Iterator[Batch]: ...
    def summaries(self) -> dict[str, pa.Table]: ...
    def evidence(self) -> dict: ...
    def model_features(self, schema: pa.Schema) -> dict: ...

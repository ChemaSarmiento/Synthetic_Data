"""Local Parquet adapter. Atomic publication of each file, never overwrite a run."""

import hashlib
import json
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq


def write_json(path: Path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ParquetOutput:
    def __init__(self, root: Path):
        self.root = root
        self.files = []

    def write(self, relative: str, table: pa.Table):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".parquet.tmp")
        pq.write_table(table, temporary, compression="zstd", compression_level=3, row_group_size=64_000)
        temporary.replace(path)
        self.files.append({"path": relative, "rows": table.num_rows, "bytes": path.stat().st_size, "sha256": sha256(path)})

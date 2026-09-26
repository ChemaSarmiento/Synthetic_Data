"""Shared artifact integrity, then validation delegated to the registered domain."""

import json
from pathlib import Path
import pyarrow.parquet as pq

from synthetic_engine.checks import require
from synthetic_engine.config import Config
from synthetic_engine.outputs.parquet import sha256
from synthetic_engine.registry import get_domain


def validate(root: Path):
    manifest = json.loads((root / "manifest.json").read_text())
    require(manifest["schema_version"] in {"0.1.0", "0.2.0"}, "unsupported manifest schema")
    require(manifest["status"] in {"validating", "complete"}, "run is incomplete")
    definition = get_domain(Config.from_dict(manifest["config"]).domain)
    expected_layout = {"event_table": definition.event_table, "partition_key": definition.partition_key}
    require(manifest.get("layout", expected_layout) == expected_layout, "domain output layout")
    inventory = manifest["files"]
    expected = {f["path"] for f in inventory}
    actual = {str(p.relative_to(root)) for p in root.rglob("*.parquet")}
    require(len(expected) == len(inventory), "duplicate inventory paths")
    require(expected == actual, "Parquet inventory differs from manifest")
    for item in inventory:
        path = root / item["path"]
        require(path.resolve().is_relative_to(root.resolve()), "artifact escapes run directory")
        require(path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"], f"file checksum {item['path']}")
        require(pq.ParquetFile(path).metadata.num_rows == item["rows"], "file row count")
    for name, digest in manifest.get("metadata_checksums", {}).items():
        path = root / name
        require(path.resolve().is_relative_to(root.resolve()), "metadata escapes run directory")
        require(sha256(path) == digest, f"metadata checksum {name}")
    rows = sum(f["rows"] for f in inventory if f["path"].startswith(definition.event_table + "/"))
    require(rows == manifest["config"]["rows"], "total requested rows")
    report = definition.validator(root, manifest)
    require(report.get("passed") is True, "domain validation did not pass")
    return {**report, "rows": rows, "domain": definition.name,
            "artifact_checks": ["inventory", "checksums", "Parquet row counts", "metadata checksums"]}

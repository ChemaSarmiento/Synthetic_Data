"""Sequential validated populations, bounded scratch, minimum transaction bytes."""
from dataclasses import replace
import gc
import json
import os
from pathlib import Path
import re
import tempfile
import time

from synthetic_engine.config import Config
from synthetic_engine.engine import generate
from synthetic_engine.outputs.parquet import sha256, write_json
from run_pilot import upload


def run(config, bucket, execution, scratch, target_bytes=10_000_000_000,
        max_shards=160, generate_fn=generate, upload_fn=upload):
    if type(target_bytes) is not int or target_bytes < 1:
        raise ValueError("target_bytes must be positive integer")
    if type(max_shards) is not int or not 1 <= max_shards <= 160:
        raise ValueError("max_shards must be between 1 and 160")
    if not 1 <= config.rows <= 1_000_000 or config.domain != "banking":
        raise ValueError("Bulk runner requires banking shards of at most 1m rows")
    if not config.parameters.get("scenarios", {}).get("aml", {}).get("enabled", False):
        raise ValueError("Bulk AML runner requires AML enabled")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", execution):
        raise ValueError("Invalid execution namespace")
    prefix = f"datasets/{execution}"
    start = time.monotonic()
    report = {"schema_version": "aml-sharded-1", "status": "generating",
              "target_transaction_bytes": target_bytes, "transaction_bytes": 0,
              "all_parquet_bytes": 0, "rows": 0, "shards": [],
              "identity_key": ["shard_id", "local_entity_id"],
              "layout": "Independent populations; hive shard_id partitions; no cross-shard histories or graph edges",
              "reference_fit": False}
    scratch.mkdir(parents=True, exist_ok=True)
    for index in range(max_shards):
        if time.monotonic() - start > 3.5 * 3600:
            raise RuntimeError("Bulk time budget reached before target completion")
        shard = f"{index:04d}"
        # TemporaryDirectory only deletes this attempt's owned directory.
        with tempfile.TemporaryDirectory(prefix="aml-shard-", dir=scratch) as temp:
            root = Path(temp) / "dataset"
            manifest = generate_fn(replace(config, seed=config.seed + index), root)
            if manifest["status"] != "complete":
                raise ValueError("Refusing unvalidated shard")
            tx_bytes = sum(f["bytes"] for f in manifest["files"] if f["path"].startswith("transactions/"))
            if tx_bytes <= 0:
                raise ValueError("Shard has no transaction bytes")
            shard_prefix = f"{prefix}/shard_id={shard}"
            paths = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "manifest.json")
            for path in paths + [root / "manifest.json"]:
                upload_fn(bucket, shard_prefix + "/" + path.relative_to(root).as_posix(), path)
            report["shards"].append({"shard_id": shard, "prefix": shard_prefix,
                                      "seed": config.seed + index, "rows": config.rows,
                                      "transaction_bytes": tx_bytes,
                                      "manifest_sha256": sha256(root / "manifest.json")})
            report["transaction_bytes"] += tx_bytes
            report["all_parquet_bytes"] += sum(f["bytes"] for f in manifest["files"])
            report["rows"] += config.rows
        gc.collect()
        print(json.dumps({"completed_shards": len(report["shards"]), "rows": report["rows"],
                          "transaction_bytes": report["transaction_bytes"],
                          "target_transaction_bytes": target_bytes}), flush=True)
        if report["transaction_bytes"] >= target_bytes:
            report["status"] = "complete"
            report["elapsed_seconds"] = time.monotonic() - start
            with tempfile.TemporaryDirectory(prefix="aml-manifest-", dir=scratch) as temp:
                marker = Path(temp) / "dataset.json"
                write_json(marker, report)
                upload_fn(bucket, prefix + "/dataset.json", marker)
            return report
    raise RuntimeError("Shard limit reached; target not met; no dataset completion marker published")


def main():
    report = run(Config.load(Path("/app/config.json")), os.environ["OUTPUT_BUCKET"],
                 os.environ["CLOUD_RUN_EXECUTION"], Path("/tmp/aml-bulk"))
    print(json.dumps({"status": report["status"], "rows": report["rows"],
                      "transaction_bytes": report["transaction_bytes"]}), flush=True)


if __name__ == "__main__":
    main()

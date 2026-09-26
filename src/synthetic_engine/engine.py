"""Local orchestration, progress records, provenance and run metrics."""

from importlib.resources import files
import importlib.metadata
import json
from pathlib import Path
import resource
import subprocess
import time

from synthetic_engine import __version__
from synthetic_engine.config import Config
from synthetic_engine.core import Domain
from synthetic_engine.domains.banking import BankingDomain
from synthetic_engine.output import ParquetOutput, sha256, write_json
from synthetic_engine.validation import validate


def git_revision():
    root = Path(__file__).resolve().parents[2]
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, stderr=subprocess.DEVNULL, text=True).strip())
        return {"commit": revision, "working_tree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "working_tree_dirty": None}


def generate(config: Config, root: Path):
    start = time.perf_counter()
    # Validate population/memory limits before creating an output directory.
    domain: Domain = BankingDomain(config)
    root.mkdir(parents=True, exist_ok=False)
    writer = ParquetOutput(root)
    evidence = json.loads(files("synthetic_engine").joinpath("evidence/banking-v1.json").read_text())
    manifest = {
        "schema_version": "0.1.0", "engine_version": __version__, "status": "generating",
        "config": config.to_dict(), "git": git_revision(), "evidence_profile": evidence["profile_id"],
        "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "pyarrow")},
        "source_checksums": {str(p.relative_to(Path(__file__).parent)): sha256(p) for p in sorted(Path(__file__).parent.rglob("*.py"))},
        "files": writer.files,
    }
    write_json(root / "manifest.json", manifest)
    write_json(root / "evidence.json", evidence)
    count = 0
    try:
        for name, table in domain.dimensions().items():
            writer.write(f"dimensions/{name}.parquet", table)
        for batch_index, batch in enumerate(domain.batches()):
            partition = f"event_date={batch.partition}/part-{batch_index:06d}.parquet"
            writer.write("transactions/" + partition, batch.events)
            writer.write("ground_truth/" + partition, batch.truth)
            if batch_index == 0:
                excluded = {"transaction_id", "timestamp", "sender_account_id", "receiver_account_id", "sender_bank_id", "receiver_bank_id"}
                write_json(root / "model_features.json", {
                    "transaction_features": [name for name in batch.events.column_names if name not in excluded],
                    "excluded_identifiers": sorted(excluded),
                    "target": "ground_truth.is_laundering",
                    "notes": "Fit encoding/scaling on training data only. Chronological split required. Do not join whole-window summaries into transaction prediction features.",
                })
                write_json(root / "schema.json", {field.name: str(field.type) for field in batch.events.schema})
            count += batch.events.num_rows
            write_json(root / "progress.json", {"rows_written": count, "last_partition": batch.partition, "resumable": False})
        for name, table in domain.summaries().items():
            writer.write(f"summaries/{name}.parquet", table)
        generated = time.perf_counter()
        manifest["status"] = "validating"
        write_json(root / "manifest.json", manifest)
        report = validate(root)
        write_json(root / "validation.json", report)
        manifest["status"] = "complete"
        manifest["metrics"] = {
            "generation_seconds": generated - start,
            "validation_seconds": time.perf_counter() - generated,
            "parquet_bytes": sum(f["bytes"] for f in writer.files),
            "peak_process_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "rss_note": "Linux process high-water mark; includes validation and prior work in this process",
        }
        write_json(root / "manifest.json", manifest)
        return manifest
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        write_json(root / "manifest.json", manifest)
        raise

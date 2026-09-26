"""Local orchestration, progress records, provenance and run metrics."""

import importlib.metadata
from pathlib import Path
import platform
import resource
import subprocess
import time

from synthetic_engine import __version__
from synthetic_engine.config import Config
from synthetic_engine.core import Domain
from synthetic_engine.registry import get_domain
from synthetic_engine.outputs.parquet import ParquetOutput, safe_segment, sha256, write_json
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
    definition = get_domain(config.domain)
    domain: Domain = definition.factory(config)
    evidence = domain.evidence()
    if not isinstance(evidence.get("profile_id"), str) or type(evidence.get("empirically_calibrated")) is not bool:
        raise ValueError("Domain evidence requires profile_id and explicit empirically_calibrated status")
    if not isinstance(evidence.get("sources"), list) or not isinstance(evidence.get("assumptions"), (dict, list)):
        raise ValueError("Domain evidence requires sources and explicit assumptions")
    root.mkdir(parents=True, exist_ok=False)
    writer = ParquetOutput(root)
    source_root = Path(__file__).resolve().parents[2]
    lock = source_root / "uv.lock"
    manifest = {
        "schema_version": "0.2.0", "engine_version": __version__, "status": "generating",
        "domain": {"name": definition.name, "version": definition.version, "spec": definition.spec},
        "layout": {"event_table": definition.event_table, "partition_key": definition.partition_key},
        "python_version": platform.python_version(), "uv_lock_sha256": sha256(lock) if lock.exists() else None,
        "config": config.to_dict(), "git": git_revision(), "evidence_profile": evidence["profile_id"],
        "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "pyarrow")},
        "source_checksums": {str(p.relative_to(Path(__file__).parent)): sha256(p) for p in sorted(Path(__file__).parent.rglob("*.py"))},
        "files": writer.files,
    }
    write_json(root / "manifest.json", manifest)
    write_json(root / "evidence.json", evidence)
    count = 0
    event_schema = None
    truth_schema = None
    has_truth = None
    try:
        for name, table in domain.dimensions().items():
            safe_segment(name)
            writer.write(f"dimensions/{name}.parquet", table)
        for batch_index, batch in enumerate(domain.batches()):
            if not 1 <= batch.events.num_rows <= config.batch_rows or count + batch.events.num_rows > config.rows:
                raise ValueError("Domain batch violates requested row limits")
            if batch.truth is not None and batch.truth.num_rows != batch.events.num_rows:
                raise ValueError("Ground truth row count must match its event batch")
            if event_schema is None:
                event_schema = batch.events.schema
                has_truth = batch.truth is not None
                truth_schema = batch.truth.schema if has_truth else None
            elif not batch.events.schema.equals(event_schema):
                raise ValueError("Event schema changed between batches")
            if (batch.truth is not None) != has_truth or (has_truth and not batch.truth.schema.equals(truth_schema)):
                raise ValueError("Ground truth availability or schema changed between batches")
            partition = f"{definition.partition_key}={safe_segment(batch.partition)}/part-{batch_index:06d}.parquet"
            writer.write(definition.event_table + "/" + partition, batch.events)
            if batch.truth is not None:
                writer.write("ground_truth/" + partition, batch.truth)
            if batch_index == 0:
                feature_metadata = domain.model_features(batch.events.schema)
                if not set(feature_metadata["features"]).issubset(batch.events.column_names):
                    raise ValueError("Domain features are not present in its event schema")
                write_json(root / "model_features.json", feature_metadata)
                write_json(root / "schema.json", {field.name: str(field.type) for field in batch.events.schema})
            count += batch.events.num_rows
            write_json(root / "progress.json", {"rows_written": count, "last_partition": batch.partition, "resumable": False})
        for name, table in domain.summaries().items():
            safe_segment(name)
            writer.write(f"summaries/{name}.parquet", table)
        if count != config.rows:
            raise ValueError("Domain did not generate the requested number of rows")
        manifest["metadata_checksums"] = {name: sha256(root / name) for name in ("evidence.json", "model_features.json", "schema.json")}
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

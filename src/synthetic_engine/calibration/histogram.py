"""Two-pass conditional histograms with training-only parameters and provenance."""

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pyarrow as pa
import pyarrow.csv as csv
import pyarrow.parquet as pq

from synthetic_engine.outputs.parquet import sha256, write_json
from synthetic_engine import __version__


@dataclass(frozen=True)
class FitConfig:
    source: dict
    value_column: str
    group_column: str
    unit: str
    transform: str = "log"
    bins: int = 128
    seed: int = 20260926
    holdout_fraction: float = 0.2
    batch_rows: int = 65_536
    max_groups: int = 256
    min_train: int = 100
    min_holdout: int = 30

    def __post_init__(self):
        if not isinstance(self.source, dict):
            raise ValueError("source must be an object")
        for key in ("id", "title", "url", "version", "license", "origin"):
            if not isinstance(self.source.get(key), str) or not self.source[key].strip():
                raise ValueError(f"source.{key} must be a nonempty string")
        if self.source["origin"] not in {"real_observations", "synthetic_benchmark", "synthetic_fixture"}:
            raise ValueError("Unsupported reference origin")
        if not all(isinstance(x, str) and x.strip() for x in (self.value_column, self.group_column, self.unit)):
            raise ValueError("Column names and units must be explicit")
        if self.value_column == self.group_column or self.transform not in {"log", "identity"}:
            raise ValueError("Require distinct columns and log or identity transform")
        for key in ("bins", "seed", "batch_rows", "max_groups", "min_train", "min_holdout"):
            if type(getattr(self, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if not 2 <= self.bins <= 1024 or not 0 <= self.seed < 2**64:
            raise ValueError("Invalid bin count or seed")
        if not 1 <= self.batch_rows <= 1_000_000 or not 1 <= self.max_groups <= 4096:
            raise ValueError("Invalid memory limits")
        if self.min_train < 2 or self.min_holdout < 1:
            raise ValueError("Invalid minimum sample counts")
        if isinstance(self.holdout_fraction, bool) or not isinstance(self.holdout_fraction, (int, float)) or not 0 < self.holdout_fraction < 1:
            raise ValueError("holdout_fraction must be between zero and one")


def reference_files(source: Path):
    if source.is_file():
        paths = [source]
    elif source.is_dir():
        paths = sorted(p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in {".csv", ".parquet"})
    else:
        raise ValueError(f"Reference input does not exist: {source}")
    if not paths or any(p.suffix.lower() not in {".csv", ".parquet"} for p in paths):
        raise ValueError("Reference input must contain CSV or Parquet files")
    return paths


def inventory(source: Path, paths):
    base = source if source.is_dir() else source.parent
    return [{"path": str(p.relative_to(base)), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in paths]


def batches(paths, value_column, group_column, batch_rows):
    columns = [value_column, group_column]
    for path in paths:
        if path.suffix.lower() == ".csv":
            reader = csv.open_csv(path, read_options=csv.ReadOptions(block_size=2**20),
                                  convert_options=csv.ConvertOptions(include_columns=columns,
                                      column_types={value_column: pa.float64(), group_column: pa.string()}))
        else:
            reader = pq.ParquetFile(path).iter_batches(batch_size=batch_rows, columns=columns)
        try:
            for batch in reader:
                for begin in range(0, batch.num_rows, batch_rows):
                    piece = batch.slice(begin, batch_rows)
                    values = piece.column(value_column).cast(pa.float64()).to_numpy(zero_copy_only=False)
                    groups = piece.column(group_column).cast(pa.string()).to_pylist()
                    if any(g is not None and len(g) > 128 for g in groups):
                        raise ValueError("Group labels exceed 128 characters; do not group by identifiers")
                    yield values, np.array([g if g is not None else "" for g in groups])
        finally:
            if hasattr(reader, "close"):
                reader.close()


def holdout_mask(offset, count, seed, fraction):
    """SplitMix64 on global row index; stable across reader batch boundaries."""
    x = np.arange(offset, offset + count, dtype=np.uint64) + np.uint64(seed)
    x = x + np.uint64(0x9E3779B97F4A7C15)
    x = (x ^ (x >> 30)) * np.uint64(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> 27)) * np.uint64(0x94D049BB133111EB)
    x = x ^ (x >> 31)
    return (x >> 11).astype(np.float64) / 2**53 < fraction


def valid_values(values, groups, transform):
    result = np.isfinite(values) & (groups != "")
    if transform == "log":
        result &= values > 0
    return result


def transformed(values, transform):
    return np.log(values) if transform == "log" else values


def bin_counts(values, model):
    edges = np.asarray(model["edges"])
    if len(edges) == 1:
        return np.array([len(values)], dtype=np.int64), int(np.count_nonzero(~np.isclose(values, edges[0], rtol=1e-12, atol=1e-12)))
    indices = np.clip(np.searchsorted(edges, values, side="right") - 1, 0, len(edges) - 2)
    outside = int(np.count_nonzero((values < edges[0]) | (values > edges[-1])))
    return np.bincount(indices, minlength=len(edges) - 1), outside


def model_digest(profile):
    data = {key: value for key, value in profile.items() if key != "profile_sha256"}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_profile(path: Path):
    profile = json.loads(path.read_text())
    if profile.get("schema_version") != "histogram-1" or profile.get("status") != "complete":
        raise ValueError("Unsupported or incomplete calibration profile")
    if model_digest(profile) != profile.get("profile_sha256"):
        raise ValueError("Calibration profile digest mismatch")
    config = FitConfig(**profile["fit_config"])
    for model in profile["groups"].values():
        if model["status"] != "fitted":
            continue
        edges = np.asarray(model["edges"], dtype=float)
        counts = np.asarray(model["counts"], dtype=float)
        if len(edges) < 1 or len(counts) != max(1, len(edges) - 1) or not np.all(np.isfinite(edges)) or not np.all(np.isfinite(counts)):
            raise ValueError("Invalid histogram shape or nonfinite parameters")
        if model["train_count"] < config.min_train or np.any(np.diff(edges) <= 0) or np.any(counts < 0) or np.any(counts != np.floor(counts)) or counts.sum() != model["train_count"]:
            raise ValueError("Invalid histogram probabilities or edges")
    return profile


def sample(model, count, rng, transform):
    if model["status"] != "fitted":
        raise ValueError("Cannot sample an unfitted reference group")
    edges = np.asarray(model["edges"])
    if len(edges) == 1:
        values = np.full(count, edges[0])
    else:
        probabilities = np.asarray(model["counts"], dtype=float) / model["train_count"]
        index = rng.choice(len(probabilities), count, p=probabilities)
        values = rng.uniform(edges[index], edges[index + 1])
    return np.exp(values) if transform == "log" else values


def diagnostics(counts, outside, model, minimum):
    total = int(np.sum(counts))
    expected = np.asarray(model["counts"], dtype=float) / model["train_count"]
    return {
        "count": total, "status": "evaluated" if total >= minimum else "insufficient_data",
        "bin_total_variation": float(np.abs(counts / total - expected).sum() / 2) if total else None,
        "outside_training_support_fraction": outside / total if total else None,
    }


def fit(source: Path, config: FitConfig, output: Path):
    if output.exists():
        raise FileExistsError(output)
    paths = reference_files(source)
    source_inventory = inventory(source, paths)
    models = {}
    audit = {"rows": 0, "valid_rows": 0, "invalid_rows": 0, "missing_group_rows": 0}
    offset = 0
    for values, groups in batches(paths, config.value_column, config.group_column, config.batch_rows):
        holdout = holdout_mask(offset, len(values), config.seed, config.holdout_fraction)
        valid = valid_values(values, groups, config.transform)
        audit["rows"] += len(values)
        audit["valid_rows"] += int(valid.sum())
        audit["invalid_rows"] += int((~valid).sum())
        audit["missing_group_rows"] += int((groups == "").sum())
        for group in np.unique(groups[groups != ""]):
            if group not in models:
                if len(models) >= config.max_groups:
                    raise ValueError("Reference group cardinality exceeds max_groups")
                models[str(group)] = {"train_count": 0, "holdout_count": 0, "invalid_count": 0, "minimum": None, "maximum": None}
            model = models[str(group)]
            member = groups == group
            training = member & valid & ~holdout
            model["train_count"] += int(training.sum())
            model["holdout_count"] += int((member & valid & holdout).sum())
            model["invalid_count"] += int((member & ~valid).sum())
            if training.any():
                data = transformed(values[training], config.transform)
                lo, hi = float(data.min()), float(data.max())
                model["minimum"] = lo if model["minimum"] is None else min(lo, model["minimum"])
                model["maximum"] = hi if model["maximum"] is None else max(hi, model["maximum"])
        offset += len(values)
    for model in models.values():
        if model["train_count"] < config.min_train:
            model["status"] = "insufficient_training"
            continue
        lo, hi = model["minimum"], model["maximum"]
        if not np.isfinite(hi - lo):
            raise ValueError("Reference numeric range exceeds supported floating-point width")
        model.update(status="fitted", edges=[lo] if lo == hi else np.unique(np.linspace(lo, hi, config.bins + 1)).tolist())
        model["counts"] = np.zeros(max(1, len(model["edges"]) - 1), dtype=np.int64)
    fitted = {k: v for k, v in models.items() if v["status"] == "fitted"}
    if not fitted:
        raise ValueError("No reference group has sufficient training data")
    held_counts = {k: np.zeros_like(v["counts"]) for k, v in fitted.items()}
    outside = {k: 0 for k in fitted}
    offset = 0
    for values, groups in batches(paths, config.value_column, config.group_column, config.batch_rows):
        holdout = holdout_mask(offset, len(values), config.seed, config.holdout_fraction)
        valid = valid_values(values, groups, config.transform)
        for group in np.unique(groups[valid]):
            if group not in fitted:
                continue
            model = fitted[str(group)]
            member = (groups == group) & valid
            counts, _ = bin_counts(transformed(values[member & ~holdout], config.transform), model)
            model["counts"] += counts
            counts, extra = bin_counts(transformed(values[member & holdout], config.transform), model)
            held_counts[str(group)] += counts
            outside[str(group)] += extra
        offset += len(values)
    if reference_files(source) != paths or inventory(source, paths) != source_inventory:
        raise ValueError("Reference files changed during calibration")
    holdout_report = {}
    for group, model in fitted.items():
        if int(model["counts"].sum()) != model["train_count"]:
            raise ValueError("Reference row accounting changed between passes")
        holdout_report[group] = diagnostics(held_counts[group], outside[group], model, config.min_holdout)
        model["counts"] = model["counts"].tolist()
    stored_config = asdict(config)
    stored_config.pop("batch_rows")  # Operational batch size does not change the model identity.
    profile = {
        "schema_version": "histogram-1", "status": "complete",
        "producer": {"engine_version": __version__, "python_version": platform.python_version(),
                     "numpy_version": np.__version__, "pyarrow_version": pa.__version__},
        "method": "conditional_piecewise_uniform_histogram",
        "fit_config": stored_config, "source_files": source_inventory,
        "split": "splitmix64_global_row_index_v1", "audit": audit,
        "groups": models, "holdout": holdout_report,
        "limitations": ["Univariate conditional fit only", "Row holdout is not future-time or account holdout", "Source origin does not establish real-world fidelity", "Sampling interpolates within transformed bins"],
    }
    profile["profile_sha256"] = model_digest(profile)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "profile.json", profile)
    write_json(output / "report.json", {"source": config.source, "audit": audit, "holdout": holdout_report,
                                      "batch_rows": config.batch_rows, "profile_sha256": profile["profile_sha256"]})
    return profile


def compare(source: Path, profile: dict, value_column: str, group_column: str,
            mapping: dict, scale: float = 1.0, batch_rows: int = 65_536):
    """Compare generated values to the frozen training histogram, not to a refit."""
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Scale must be finite and positive")
    if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
        raise ValueError("Mapping must contain string group names")
    config = FitConfig(**profile["fit_config"])
    counts = {}
    outside = {}
    unknown = {}
    invalid = 0
    paths = reference_files(source)
    source_inventory = inventory(source, paths)
    for values, raw_groups in batches(paths, value_column, group_column, batch_rows):
        values = values * scale
        valid = valid_values(values, raw_groups, config.transform)
        invalid += int((~valid).sum())
        for raw in np.unique(raw_groups[valid]):
            group = mapping.get(str(raw), str(raw))
            selected = (raw_groups == raw) & valid
            model = profile["groups"].get(group)
            if model is None or model["status"] != "fitted":
                unknown[str(raw)] = unknown.get(str(raw), 0) + int(selected.sum())
                continue
            hist, extra = bin_counts(transformed(values[selected], config.transform), model)
            counts[group] = counts.get(group, np.zeros_like(hist)) + hist
            outside[group] = outside.get(group, 0) + extra
    if reference_files(source) != paths or inventory(source, paths) != source_inventory:
        raise ValueError("Comparison input changed during evaluation")
    return {"profile_sha256": profile["profile_sha256"], "input_files": source_inventory,
            "value_column": value_column, "group_column": group_column, "scale": scale, "mapping": mapping,
            "groups": {k: diagnostics(v, outside[k], profile["groups"][k], config.min_holdout) for k, v in counts.items()},
            "unmatched_groups": unknown, "invalid_rows": invalid,
            "limitations": "Marginal conditional distribution comparison only; no automatic fidelity acceptance threshold."}

"""Bounded categorical/time reference profiling; no domain-specific semantics."""
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as csv
import pyarrow.parquet as pq

from synthetic_engine.calibration.histogram import inventory, reference_files, model_digest
from synthetic_engine.outputs.parquet import write_json


def profile_categories(source: Path, output: Path, columns: list[str], timestamp: str,
                       timestamp_format: str, source_metadata: dict, max_cells: int = 100_000):
    if output.exists():
        raise FileExistsError(output)
    if not columns or len(set(columns + [timestamp])) != len(columns) + 1:
        raise ValueError("Require distinct category and timestamp columns")
    if type(max_cells) is not int or not 1 <= max_cells <= 1_000_000:
        raise ValueError("max_cells must be between 1 and 1000000")
    for key in ("id", "url", "version", "license", "origin"):
        if not isinstance(source_metadata.get(key), str) or not source_metadata[key]:
            raise ValueError(f"source.{key} is required")
    paths = reference_files(source)
    before = inventory(source, paths)
    joint, daily = Counter(), Counter()
    marginals = {c: Counter() for c in columns}
    rows = invalid = 0
    earliest = latest = None
    selected = columns + [timestamp]
    for path in paths:
        reader = (csv.open_csv(path, read_options=csv.ReadOptions(block_size=2**20),
                  convert_options=csv.ConvertOptions(include_columns=selected,
                                  column_types={c: pa.string() for c in selected}))
                  if path.suffix.lower() == ".csv" else
                  pq.ParquetFile(path).iter_batches(batch_size=65536, columns=selected))
        try:
            for batch in reader:
                arrays = [batch.column(c).cast(pa.string()).to_pylist() for c in selected]
                # Timestamp parsing cache is limited to this input batch.
                parsed = {}
                for values in zip(*arrays):
                    rows += 1
                    if any(v is None or not v.strip() for v in values):
                        invalid += 1
                        continue
                    if any(len(v) > 128 for v in values):
                        raise ValueError("Category/timestamp exceeds 128 characters")
                    raw_time = values[-1]
                    if raw_time not in parsed:
                        try:
                            parsed[raw_time] = datetime.strptime(raw_time, timestamp_format)
                        except ValueError:
                            parsed[raw_time] = None
                    instant = parsed[raw_time]
                    if instant is None:
                        invalid += 1
                        continue
                    if instant.tzinfo is not None:
                        raise ValueError("Use timezone-naive source timestamps; timezone conversion is not implemented")
                    key = (*values[:-1], instant.weekday(), instant.hour)
                    day = instant.date().isoformat()
                    if (key not in joint and len(joint) >= max_cells) or (day not in daily and len(daily) >= max_cells):
                        raise ValueError("Profile cardinality exceeds max_cells")
                    joint[key] += 1
                    daily[day] += 1
                    for c, value in zip(columns, values[:-1]):
                        marginals[c][value] += 1
                    earliest = instant if earliest is None else min(earliest, instant)
                    latest = instant if latest is None else max(latest, instant)
        finally:
            if hasattr(reader, "close"):
                reader.close()
    if not joint:
        raise ValueError("No valid rows to profile")
    if reference_files(source) != paths or inventory(source, paths) != before:
        raise ValueError("Reference files changed during profiling")
    # Include zero-event dates between observed endpoints. Endpoints may be partial.
    span = (latest.date() - earliest.date()).days + 1
    if span > max_cells:
        raise ValueError("Calendar span exceeds max_cells")
    exposure = Counter((earliest.date() + timedelta(days=i)).weekday() for i in range(span))
    weekday_counts = Counter()
    for key, count in joint.items():
        weekday_counts[key[-2]] += count
    result = {
        "schema_version": "categorical-time-1", "status": "complete",
        "source": source_metadata, "source_files": before,
        "columns": columns, "timestamp_column": timestamp, "timestamp_format": timestamp_format,
        "timezone": "unspecified_source_wall_clock", "weekday_encoding": "Monday=0",
        "audit": {"rows": rows, "valid_rows": rows-invalid, "invalid_rows": invalid},
        "observed_start": earliest.isoformat(), "observed_end": latest.isoformat(),
        "marginals": {c: dict(sorted(v.items())) for c, v in marginals.items()},
        "daily_counts": dict(sorted(daily.items())),
        "weekday_exposure_days": dict(sorted(exposure.items())),
        "weekday_mean_rows_per_calendar_day": {k: weekday_counts[k]/v for k, v in sorted(exposure.items())},
        "joint_dimensions": columns + ["source_weekday", "source_hour"],
        "joint_counts": [{"values": list(k), "count": v} for k, v in sorted(joint.items())],
        "limitations": ["Descriptive full-source profile, not a held-out fitted model",
                        "Source timezone unknown; hours are not UTC or customer-local hours",
                        "Observed endpoints may be partial; calendar exposure is inferred, not confirmed",
                        "No account, recurrence, seasonality or real-world fidelity inference",
                        "Not applied to generation; payment-category semantic mapping remains required"],
    }
    result["profile_sha256"] = model_digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result

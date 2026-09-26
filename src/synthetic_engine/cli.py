"""Command line interface; all commands operate on local files only."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from synthetic_engine.config import Config
from synthetic_engine.engine import generate
from synthetic_engine.validation import validate
from synthetic_engine.registry import list_domains
from synthetic_engine.calibration.histogram import FitConfig, fit, compare, load_profile
from synthetic_engine.outputs.parquet import write_json


def main():
    parser = argparse.ArgumentParser(prog="synthetic-engine")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("domains", help="List registered domains and their specifications")
    calibration = sub.add_parser("calibrate", help="Fit a local reference numeric profile with holdout diagnostics")
    calibration.add_argument("--input", type=Path, required=True)
    calibration.add_argument("--config", type=Path, required=True)
    calibration.add_argument("--output", type=Path, required=True)
    comparison = sub.add_parser("compare", help="Compare generated values against a frozen reference profile")
    comparison.add_argument("--input", type=Path, required=True)
    comparison.add_argument("--profile", type=Path, required=True)
    comparison.add_argument("--value-column", required=True)
    comparison.add_argument("--group-column", required=True)
    comparison.add_argument("--mapping", type=Path)
    comparison.add_argument("--scale", type=float, default=1.0)
    comparison.add_argument("--output", type=Path, required=True, help="New JSON report file")
    gen = sub.add_parser("generate", help="Generate and validate a new local Parquet dataset")
    gen.add_argument("--config", type=Path, required=True)
    gen.add_argument("--output", type=Path, required=True, help="New directory; existing directories are never overwritten")
    gen.add_argument("--rows", type=int)
    check = sub.add_parser("validate", help="Independently validate an existing complete dataset")
    check.add_argument("output", type=Path)
    estimate = sub.add_parser("estimate", help="Extrapolate a completed pilot, not a cloud cost quote")
    estimate.add_argument("output", type=Path)
    estimate.add_argument("--target-gb", type=float, default=15.0, help="Decimal GB of all Parquet tables")
    args = parser.parse_args()
    try:
        if args.command == "domains":
            print(json.dumps(list_domains(), indent=2))
        elif args.command == "calibrate":
            config = FitConfig(**json.loads(args.config.read_text()))
            profile = fit(args.input, config, args.output)
            print(json.dumps({"output": str(args.output), "profile_sha256": profile["profile_sha256"],
                              "audit": profile["audit"], "groups": len(profile["groups"])}, indent=2))
        elif args.command == "compare":
            if args.output.exists():
                raise FileExistsError(args.output)
            profile = load_profile(args.profile)
            mapping = json.loads(args.mapping.read_text()) if args.mapping else {}
            report = compare(args.input, profile, args.value_column, args.group_column, mapping, args.scale)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, report)
            print(json.dumps({"output": str(args.output), "groups": report["groups"],
                              "unmatched_groups": report["unmatched_groups"]}, indent=2))
        elif args.command == "generate":
            config = Config.load(args.config)
            if args.rows is not None:
                config = replace(config, rows=args.rows)
            result = generate(config, args.output)
            print(json.dumps({"output": str(args.output), "status": result["status"], "rows": config.rows, **result["metrics"]}, indent=2))
        elif args.command == "validate":
            print(json.dumps(validate(args.output), indent=2))
        else:
            if not 0 < args.target_gb < 1_000_000:
                raise ValueError("target-gb must be finite and positive")
            result = json.loads((args.output / "manifest.json").read_text())
            if result["status"] != "complete":
                raise ValueError("A completed pilot is required")
            metrics = result["metrics"]
            ratio = args.target_gb * 1e9 / metrics["parquet_bytes"]
            print(json.dumps({
                "target_parquet_bytes": int(args.target_gb * 1e9),
                "rough_rows": round(result["config"]["rows"] * ratio),
                "rough_generation_seconds": metrics["generation_seconds"] * ratio,
                "rough_validation_seconds": metrics["validation_seconds"] * ratio,
                "limitations": "Linear pilot extrapolation only. Compression, fixed dimensions, file sizes, population and hardware change results. Not an executable plan or GCP cost estimate. Domain-specific resource limits still apply.",
            }, indent=2))
        return 0
    except (ValueError, TypeError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Command line interface; all commands operate on local files only."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from synthetic_engine.config import Config
from synthetic_engine.engine import generate
from synthetic_engine.validation import validate


def main():
    parser = argparse.ArgumentParser(prog="synthetic-engine")
    sub = parser.add_subparsers(dest="command", required=True)
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
        if args.command == "generate":
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
                "limitations": "Linear pilot extrapolation only. Compression, fixed dimensions, file sizes, population and hardware change results. Not an executable plan or GCP cost estimate. Daily row safety limits still apply.",
            }, indent=2))
        return 0
    except (ValueError, TypeError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

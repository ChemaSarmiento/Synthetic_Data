"""Normalize payment semantics of a local exploratory sample, up to 10,000 rows."""
import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq

from synthetic_engine.domains.banking.payments import normalize_ibm_formats
from synthetic_engine.outputs.parquet import sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if not 1 <= pq.ParquetFile(args.input).metadata.num_rows <= 10_000:
        raise ValueError("Require an exploratory sample of 1 to 10000 rows")
    before = sha256(args.input)
    table = normalize_ibm_formats(pq.read_table(args.input))
    if sha256(args.input) != before:
        raise ValueError("Input changed during normalization")
    args.output.mkdir(parents=True, exist_ok=False)
    path = args.output / "normalized.parquet"
    pq.write_table(table, path, compression="zstd")
    report = dict(payment_schema_version=2, rows=len(table), input_sha256=before,
                  output_sha256=sha256(path), source_format_counts={},
                  scope="Reference normalization only; not a generated banking dataset or fitted model")
    for value in table.column("source_payment_format").to_pylist():
        report["source_format_counts"][value] = report["source_format_counts"].get(value, 0) + 1
    write_json(args.output / "manifest.json", report)
    print(json.dumps({"rows": len(table), "formats": len(report["source_format_counts"]), "output": str(args.output)}))


if __name__ == "__main__":
    main()

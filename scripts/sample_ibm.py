"""Create a bounded, reproducible exploratory sample from the registered IBM CSV."""
import argparse
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.csv as csv
import pyarrow.parquet as pq

from synthetic_engine.outputs.parquet import sha256, write_json


def sample(source, metadata, output, rows=10_000, seed=20260926):
    if output.exists():
        raise FileExistsError(output)
    if type(rows) is not int or not 7 <= rows <= 10_000:
        raise ValueError("Exploratory sample size must be between 7 and 10000")
    digest = sha256(source)
    if digest != metadata["sha256"]:
        raise ValueError("Input does not match registered source")
    populations = metadata["observed_statistics"]["payment_format_counts"]
    groups = sorted(populations)
    if rows < len(groups) or rows > sum(populations.values()):
        raise ValueError("Sample budget cannot cover source groups")
    # Equal allocation protects rare formats. Weights restore population proportions.
    quotas = {g: min(populations[g], rows // len(groups) + (i < rows % len(groups)))
              for i, g in enumerate(groups)}
    if sum(quotas.values()) != rows:
        raise ValueError("Source group too small for equal allocation")
    columns = ["Timestamp", "Payment Currency", "Payment Format", "Amount Paid", "Is Laundering"]
    rng = np.random.default_rng(seed)
    keys = {g: np.array([], dtype=float) for g in groups}
    tables = {g: None for g in groups}
    observed = {g: 0 for g in groups}
    offset = 0
    with csv.open_csv(source, read_options=csv.ReadOptions(block_size=2**20),
                      convert_options=csv.ConvertOptions(include_columns=columns,
                                      column_types={c: pa.string() for c in columns})) as reader:
        for batch in reader:
            table = pa.Table.from_batches([batch]).append_column(
                "source_row_index", pa.array(np.arange(offset, offset + len(batch))))
            offset += len(batch)
            priorities = rng.random(len(batch))
            formats = np.array(batch.column("Payment Format").to_pylist())
            if set(np.unique(formats)) - set(groups):
                raise ValueError("Unknown source format")
            for g in groups:
                index = np.flatnonzero(formats == g)
                observed[g] += len(index)
                candidate = table.take(pa.array(index))
                merged = candidate if tables[g] is None else pa.concat_tables([tables[g], candidate])
                rank = np.concatenate([keys[g], priorities[index]])
                chosen = np.argsort(rank, kind="stable")[:quotas[g]]
                tables[g] = merged.take(pa.array(chosen))
                keys[g] = rank[chosen]
    if observed != populations or sha256(source) != digest:
        raise ValueError("Source inventory/counts changed")
    pieces = [tables[g].append_column("sampling_weight", pa.array([populations[g]/quotas[g]] * quotas[g]))
              for g in groups]
    result = pa.concat_tables(pieces).sort_by([("source_row_index", "ascending")])
    output.mkdir(parents=True, exist_ok=False)
    pq.write_table(result, output / "sample.parquet", compression="zstd")
    report = dict(source_id=metadata["id"], source_sha256=digest, source_rows=offset,
                  sample_rows=len(result), seed=seed, strata=quotas, population_counts=populations,
                  method="equal-stratum bottom-k random priorities; source-order tie breaking",
                  weight="population stratum count / sampled stratum count",
                  sample_sha256=sha256(output / "sample.parquet"),
                  limitations=["Unweighted frequencies are biased toward rare formats",
                               "Exploration only; AML labels are not sampling strata",
                               "Full CSV scanned once to avoid file-prefix sampling bias"])
    write_json(output / "manifest.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/references/ibm-aml/HI-Small_Trans.csv"))
    parser.add_argument("--metadata", type=Path, default=Path("references/banking/ibm-hi-small.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = sample(args.input, json.loads(args.metadata.read_text()), args.output)
    print(json.dumps({k: report[k] for k in ("sample_rows", "strata", "sample_sha256")}, indent=2))

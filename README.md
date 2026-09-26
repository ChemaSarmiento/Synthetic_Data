# Synthetic Data

Evidence-backed synthetic datasets, starting with banking transactions and anti-money-laundering research.

## Status

The first local Python engine is working: a banking/AML preset produces Parquet datasets, separate ground truth, account-level clustering summaries, provenance manifests, and integrity reports. No cloud workload infrastructure has been deployed.

This version uses documented simulation assumptions informed by published references. **It has not been empirically calibrated against real transactions or the IBM dataset.**

## Quick start

Requires Python 3.11+ on Linux (tested with Python 3.14).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/synthetic-engine generate --config configs/banking-demo.json --output outputs/demo
.venv/bin/synthetic-engine validate outputs/demo
.venv/bin/synthetic-engine estimate outputs/demo --target-gb 15
.venv/bin/pytest -q
```

Use a new output directory for each run. Generated data stays outside Git. For the exact tested dependency versions, install `requirements-dev.lock` before installing the project.

The demo creates 100,000 transactions across 5,000 accounts, 30 banks, five countries and 30 days. It includes 39 transaction columns, historical behavioral features, and four graph motif families with both illicit scenarios and legitimate controls. The demo's requested 0.4% illicit fraction is a testing assumption; actual prevalence is reported after rounding to complete scenarios.

See the [local engine guide](docs/local-engine.md) for table semantics, modeling guidance, memory bounds and current limitations. Automatic 15 GB targeting, fitted reference profiles, SQL/JSON outputs, cloud execution and streaming are subsequent milestones.

## Design

- Shared Python engine: reproducible seeds, bounded-memory batches, checkpoints, stable entity and event IDs.
- Domain modules: entities, relationships, temporal behavior, constraints, and scenarios; banking/AML first.
- Evidence registry: source URL, publication date, license, findings, applicability, uncertainty, and explicit assumptions.
- Calibration: learn distributions and dependencies from reference datasets; distinguish empirical estimates from literature-informed assumptions.
- Validation: relational integrity, temporal consistency, distribution fidelity, network behavior, and feature leakage checks.
- Outputs: Parquet first, then JSONL, PostgreSQL and BigQuery; Pub/Sub event replay later.

Each dataset should include a manifest recording configuration, seed, code version, source versions, row counts, byte sizes, and validation results. Simulator ground truth must remain separate from model features.

## Milestones

1. Repository, architecture, evidence contracts, and local GCP setup.
2. Banking/AML generator with a small validated sample, then approximately 15 GB of compressed Parquet.
3. Containerized batch execution, SQL and semi-structured outputs, and reviewed GCP infrastructure.
4. Streaming replay with rate control, late events, duplicates, and resumability.
5. Additional domains through the same module interface.

IBM AML data is a candidate reference and is itself synthetic. Calibration against it must not be described as calibration against real customer records.

See [GCP setup](docs/gcp-setup.md) and [evidence template](references/template.yaml).

# Synthetic Data

Evidence-backed synthetic datasets, starting with banking transactions and anti-money-laundering research.

## Status

Planning and local environment setup. No generator or cloud infrastructure has been deployed.

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

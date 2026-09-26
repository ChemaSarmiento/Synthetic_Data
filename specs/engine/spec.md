# ENG — Synthetic Engine contract v0.2

Status: implemented. Locked uv sync, wheel packaging and acceptance tests are verified on Python 3.14.4/Linux. A shared partial reference-calibration capability was added in v0.3; see [CAL](../calibration/spec.md).

## Purpose and scope

Generate reference-documented synthetic datasets for analysis, testing and model
development. Reuse orchestration, output, provenance and integrity validation
across domains. Initial execution is local Python and Parquet; cloud execution,
SQL, JSON and streaming are future adapters.

## Configuration

`Config` contains only `domain`, `seed`, `rows`, `batch_rows`, and `parameters`.
The first four belong to the engine. The domain owns its `parameters` object,
including optional scenarios. Unsupported fields and unknown domain IDs fail
before creating output. Legacy flat `banking_aml` configuration is normalized
through an explicit domain compatibility adapter.

## Domain contract

A registered `DomainDefinition` declares an ID, version, spec path, description,
factory, domain validator, event-table name and partition key. A domain implements:

- `dimensions() -> dict[str, pyarrow.Table]` (can be empty).
- `batches() -> Iterator[Batch]`; each batch has a partition, event rows and optional ground truth. Event schema, ground-truth availability and ground-truth schema remain consistent within a run.
- `summaries() -> dict[str, pyarrow.Table]` (can be empty).
- `evidence() -> dict` with a profile ID, calibration status, sources and assumptions.
- `model_features(schema) -> dict` with candidate features, excluded identifiers,
  optional target and interpretation notes.

Domain code owns entity names, financial concepts, labels, temporal semantics,
and reference profiles. The engine does not import banking generators or validators.
Only the registry's builtin registration function names the builtin domains.
Registration is explicit in Python; automatic discovery of third-party packages is deferred.

## Evidence

Every profile distinguishes measured parameters, literature-informed assumptions
and unresolved questions. References identify source URLs, applicability and
licensing where known. No source present means assumptions-only, not calibrated.
The run stores the full profile and its digest. Parameter calibration requires a
named dataset/version, fitting method and held-out diagnostics. The first v0.3
implementation provides these for conditional numeric histograms; full-domain
fidelity requires additional domain-specific evidence.

## Acceptance criteria

| ID | Requirement | Verification |
| --- | --- | --- |
| ENG-001 | uv owns dependency resolution; committed `uv.lock`; Python version documented | `uv sync --locked`, `uv lock --check` |
| ENG-002 | Register a non-banking test domain and generate/validate without modifying core | `test_non_banking_domain_uses_same_engine` |
| ENG-003 | Shared config has no banking-specific fields; reject unknown domains/options | config and registry tests |
| ENG-004 | Ground truth is optional and never implicitly used as features | unlabeled-domain and banking-baseline tests |
| ENG-005 | Same seed and versions reproduce contents regardless of output slicing | banking reproducibility test |
| ENG-006 | Outputs have manifests, evidence and integrity checks; incomplete runs fail validation | corruption and failed-run tests |
| ENG-007 | Existing output directories are never overwritten; paths cannot escape the run | overwrite and unsafe-path tests |
| ENG-008 | No deployment, credentials, local checkpoint or generated data is published | Git ignore/tracked-file inspection |

## Non-goals for v0.2

No arbitrary domain generation from a paper alone, learned calibration, arbitrary
user code loading, automatic resume, distributed execution or cost guarantee.
Spec files describe contracts; they are not executable simulation DSLs.

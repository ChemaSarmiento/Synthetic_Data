# v0.2 tasks

- [x] ENG-001: uv installation, dependency groups, Python pin and committed lock.
- [x] ENG-002/003: registry and domain-neutral config/orchestrator.
- [x] ENG-004: optional ground truth and baseline example.
- [x] Separate banking parameters, references, features and validator.
- [x] Separate optional AML scenarios and their topology validation.
- [x] ENG-005/006/007: regression, extension and failure-path tests.
- [x] Validate the existing v0.1 dataset and new v0.2 pilots.
- [x] Update usage, roadmap, spec status and local CHECKPOINT.
- [x] ENG-008: verify excluded local artifacts and prepare source-only publication.

## Verification record

- `uv sync --locked` and `uv lock --check` succeeded (uv 0.12.19).
- `uv run --locked pytest -q`: 41 passed.
- Built a wheel and checked inclusion of the registry, domain, scenario and evidence.
- Independently validated retained v0.1 data without modifying it.
- Generated banking baseline and AML pilots, 100,000 rows each.
- All 64 Parquet hashes in the AML pilot match the v0.1 pilot exactly.
- Private operational details and local paths are recorded only in CHECKPOINT.

Reference fidelity, new production domains and cloud workload deployment are not
part of the completed v0.2 acceptance criteria; see the roadmap.

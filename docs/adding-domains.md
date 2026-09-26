# Adding a reference-backed domain

A new domain should not require banking concepts or changes to the engine's run
loop. The entry point is a specification and an explicit registry entry.

1. Copy `specs/templates/domain.md` into `specs/domains/<name>/spec.md`.
   Record the objective, reference population, licenses, parameters, assumptions,
   output schema, invariants, resource bounds and acceptance criteria. Add a plan
   and tasks next to it.
2. Create `src/synthetic_engine/domains/<name>/`. Implement domain-specific
   configuration validation, generation, semantic validation and an evidence profile.
   Optional use cases go under `scenarios/`; ordinary domain data should not
   depend on a classification label.
3. Implement the `Domain` protocol from `core.py`. Return empty dimension/summary
   dictionaries where unnecessary. Yield `Batch(partition, events, truth=None)` for
   unlabelled data. Supply an explicit `model_features` contract, including
   `target: null` if no prediction target exists.
4. Expose a `definition()` returning a `DomainDefinition`. Register it in
   `registry._load_builtins()`. The registry is the composition boundary; the
   generic configuration, writer and engine must remain independent of this domain.
5. Include reference profile files through setuptools package-data declarations
   in `pyproject.toml`. Keep large reference datasets outside Git. Add a minimal
   example under `configs/<name>/`.
6. Add acceptance tests: deterministic output, configuration errors, schema and
   domain invariants, evidence status, optional labels, corruption, realistic
   dependencies and any measured reference fidelity. Register test-only domains
   in tests as demonstrated by `tests/test_domain_contract.py`.
7. Run `uv sync --locked`, `uv run --locked pytest -q` and a pilot. Record actual
   resource usage, quality results and limitations. Update spec status only when
   its acceptance criteria pass.

## Evidence profile minimum

Every run includes a profile ID, explicit `empirically_calibrated` boolean, sources
and assumptions. The engine validates that these fields exist with the required
types; it cannot verify that a paper supports a scientific claim. Review the
source-to-parameter mapping in the specification.

The [shared calibration module](calibration.md) now records source hashes, a fitting
method and row-held-out diagnostics for conditional numeric histograms. Domains can
bind those profiles to explicit parameters, as banking does for amounts. Preserve
the distinction between a partially fitted parameter and full-domain fidelity.
Joint models, uncertainty estimates and entity/time holdouts remain future work.

## Extension limits

The registry currently loads trusted in-repository Python modules. Third-party
plugin discovery, a declarative simulation language and automatic extraction of
parameters from papers are not implemented. A test fixture verifies the extension
contract; it is not a second scientifically validated domain.

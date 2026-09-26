# v0.2 implementation plan

1. Install uv outside the project environment; commit `uv.lock` and a Python pin.
   Move pytest into a development dependency group. Retire the manual lock file.
2. Introduce a domain registry. Keep the current shared modules small; add a
   dedicated `outputs/` package for the Parquet adapter.
3. Split generic configuration and integrity checks from banking parameters and
   semantic validation. Preserve old banking config loading and dataset validation.
4. Move banking under `domains/banking/`, including its evidence. Extract AML
   generation and topology checks into `domains/banking/scenarios/aml.py`.
5. Provide explicit banking baseline and banking-plus-AML example configs.
6. Prove extension using a tiny, unlabelled, non-banking test fixture. Do not
   present that fixture as a supported realistic production domain.
7. Verify old sample readability, deterministic results after migration, and both
   new examples. Update specs, roadmap and local CHECKPOINT; publish source only.

Keep numerical model changes out of this refactor. Dependency resolution may
select different compatible versions for older Python interpreters; record the
actual versions and lock digest in each run. The validated development target is
Python 3.14.4 on Linux; other runtimes require their own acceptance runs.

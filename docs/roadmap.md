# Synthetic Engine roadmap

## Current foundation

- General engine with a domain registry and shared configuration/output contracts.
- Banking domain with an optional AML scenario and unlabelled baseline.
- uv-managed development, lockfile, tests, Parquet, manifests and local validation.
- Initial specifications, acceptance criteria and domain templates.
- Shared CSV/Parquet numeric histogram fitting, source hashes and holdout diagnostics.
- First partial amount calibration against the versioned IBM synthetic benchmark.

## Next steps, in order

1. **Review the specs and the local checkpoint.** Confirm the current boundaries,
   implemented behavior and pending work. Keep private operational details local.
2. **Extend reference calibration.** The first slice fits conditional amount
   distributions against IBM HI-Small. Next specify payment-format, temporal and
   account-activity fitting, then joint/network fidelity and independent evaluation.
   IBM's AML benchmark remains a synthetic reference, not real customer data.
3. **Add a second reference-backed domain.** Select it and its source together;
   write its spec before implementation. This should exercise the common engine
   rather than copy banking code. No specific second domain has been selected.
4. **Add output adapters.** Nested JSONL and relational schema/bulk-loading support
   first; then analytical SQL integration. Keep output format separate from domain
   behavior and define adapter acceptance tests.
5. **Prepare large batch runs.** Benchmark larger pilots, add target-byte sizing,
   resumable state and bounded parallelism where needed. The approximately 15 GB
   banking/AML dataset is the first scale case, not the size of every dataset.
6. **Propose GCP batch deployment.** Present concrete resources, location,
   retention and estimated costs within the authorized MXN 400 monthly planning
   budget before creating workload resources. Budgets alert; they do not cap spend.
   Cloud Run Jobs/Storage/BigQuery remain candidates, not provisioned infrastructure.
7. **Add streaming delivery.** Specify event-time versus delivery-time behavior,
   replay rate, late/duplicate events and restart semantics. Pub/Sub is a candidate
   adapter; the domain should remain reusable for batch and streaming.

Each milestone starts with a specification or an amendment, then a plan, tasks,
implementation, acceptance tests and a measured pilot. This roadmap is not a
claim that calibration, cloud deployment, SQL or streaming already exist.

# Calibration tasks

- [x] CAL-008: IBM source registration and primary-paper review.
- [x] CAL-001/002/003/005: generic fitting, deterministic split and edge cases.
- [x] CAL-004: source inventory, model digest and evidence provenance.
- [x] CAL-006: optional banking binding and regression checks.
- [x] CAL-007: generated-data comparison and IBM pilot.
- [x] Update docs, measured results and local CHECKPOINT.

## Verification

- 57 automated tests passed, including training/holdout isolation, batch invariance,
  CSV/Parquet equivalence, generic non-banking values, profile integrity and currency binding.
- IBM HI-Small: 5,078,345 rows, 15 currencies, zero invalid amount/currency rows.
- Generated 100,000 rows with learned amounts; all five engine currencies covered.
- Conditional bin distances reduced from 0.2193–0.2944 to 0.0207–0.0298.
- Source metadata, four research notes and BibTeX entries registered.
- Raw data, fitted profiles, reports and CHECKPOINT remain local and ignored.

Reference evaluation covers amount distributions only. Full-domain calibration,
model performance and real-world transfer are not established.

## Categorical/time extension

- [x] CAL-009: generic bounded joint profiling CLI with calendar exposure and provenance.
- [x] Test categorical counts, invalid timestamps, calendar gaps and CSV/Parquet equivalence.
- [x] CAL-010: explicit IBM payment-format to engine semantics and coverage decision.
- [ ] CAL-011: training-only categorical fit, temporal holdout and generator binding.
- [ ] CAL-012: account activity, recurrence and network evaluation.

- [x] Reproducible 10,000-row stratified exploratory sample with weights and local manifest.

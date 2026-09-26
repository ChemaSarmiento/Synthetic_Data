# CAL — Reference histogram calibration v0.1

Status: implemented. Acceptance suite passes; the complete IBM HI-Small file was fitted and a 100,000-row generated pilot was compared. This validates the implemented conditional-amount workflow, not full-domain realism.

## Scope

Fit one numeric field conditionally on one categorical field from local CSV or
Parquet. This is a reusable engine capability; banking is its first consumer.
Source metadata must distinguish real observations, synthetic benchmarks and test
fixtures. The user selected IBM's synthetic AMLworld benchmark, HI-Small first.

This milestone fits conditional amount distributions, not an entire financial
world, a classifier or network topology. It does not infer countries, ownership,
currency exchange rates or AML prevalence from amounts.

## Method

Use two bounded-memory passes. A deterministic row-position hash assigns 80% to
training and 20% to holdout by default, independent of input batch boundaries.
Pass one determines training-only min/max in the specified identity or natural-log
space. Pass two counts training and holdout into fixed equal-width transformed
bins. Sampling uses training frequencies and uniform values within each bin in
transformed space. Constant groups are point masses.

Null/nonfinite values and nonpositive log inputs are counted and excluded. Missing
group labels are counted. Malformed numeric strings fail rather than guessing.
Limit group cardinality and batch size. Hash source bytes before and after fitting;
reject changed inputs. Save a profile, digest, source metadata, fitting config and
holdout diagnostics. No raw rows or identifiers belong in a learned profile.

Holdout diagnostics report bin total-variation distance, out-of-training-support
fraction and insufficient sample status. They are descriptive, not an automatic
scientific validation gate. Row-level holdout does not test future-time or
unseen-account generalization; downstream AML modeling needs different splits.

## Banking binding

Optionally load a profile through `parameters.amount_calibration`. Require
`unit=payment_currency_major` and log transformation. Map engine ISO currency
codes explicitly to reference categories. Missing groups either raise or use an
explicit preset fallback. Apply only to background principal amounts; scenario
amounts retain their documented synthetic rules. Keep country mix, relationships,
timing, FX, fees and labels unchanged. Record calibrated scope and fallbacks in
run evidence, embedding the profile so validation does not need the original file.

## Acceptance

| ID | Criterion | Verification |
| --- | --- | --- |
| CAL-001 | Same rows/config reproduce profiles across batch sizes | CSV/Parquet and batch tests |
| CAL-002 | Holdout values cannot affect fitted bins or probabilities | held-out-only mutation test |
| CAL-003 | Invalid values and small/missing groups are visible | edge-case tests |
| CAL-004 | Source bytes, origin, license, schema and scope are traceable | profile manifest and digest tests |
| CAL-005 | Generic fitting supports non-banking fields | identity-transform fixture |
| CAL-006 | Banking consumes profiles without altering uncalibrated runs | integration and legacy regression |
| CAL-007 | Evaluate actual generated values against the fixed profile | compare command and pilot report |
| CAL-008 | IBM variant/version/license and relevant papers are registered | reference catalog and research notes |

## Non-goals

No joint copula or sequence fitting, entity-aware holdout, privacy guarantee,
automatic paper-to-code extraction, GCP deployment, or real-world effectiveness
claim. IBM fitting is calibration against synthetic reference data.

# Reference calibration v0.3

The shared calibration module fits conditional numeric histograms from CSV or
Parquet. Banking currently binds it to background payment amounts by currency.
Other domains can reuse fitting, sampling and comparison without banking imports.

## Selected source and papers

The first source is IBM AMLworld's `HI-Small_Trans.csv`, catalog version 8, retrieved
2026-09-26. It is synthetic, not customer banking records. The checked file has
5,078,345 rows and 475,664,283 bytes. Exact source metadata and SHA-256 are recorded
in [the reference entry](../references/banking/ibm-hi-small.json).

IBM publishes the dataset under CDLA-Sharing-1.0, distinct from the code repository
license. Raw reference data and learned profiles remain local and outside Git.
See [research notes](../references/banking/reading-notes.md) and
[BibTeX entries](../references/banking/papers.bib) for the four reviewed papers and
their specific roles. No paper is treated as evidence for arbitrary preset values.

## Reproduce the pipeline

Download `HI-Small_Trans.csv` from the [official dataset page](https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml)
into `data/references/ibm-aml/`. Use the file digest in the reference entry to verify
the exact version. Do not assume the latest public download matches a previous run.

```sh
uv sync --locked
uv run --locked synthetic-engine calibrate \
  --input data/references/ibm-aml/HI-Small_Trans.csv \
  --config configs/calibration/ibm-hi-small.json \
  --output outputs/calibration/ibm-hi-small-v03

uv run --locked synthetic-engine generate \
  --config configs/banking/ibm-calibrated.json \
  --output outputs/banking-ibm

uv run --locked synthetic-engine compare \
  --input outputs/banking-ibm/transactions \
  --profile outputs/calibration/ibm-hi-small-v03/profile.json \
  --value-column amount_paid_minor --group-column payment_currency \
  --mapping configs/calibration/ibm-currencies.json --scale 0.01 \
  --output outputs/calibration/ibm-hi-small-v03/generated-comparison.json
```

Paths in configuration are resolved from the working directory; run these examples
from the repository root. Output directories/report files must be new. For another
reference, provide its provenance, column mapping, unit and fitting parameters.
The fitter does not verify a publisher's identity or automatically decide dataset
licensing; source metadata is an explicit input.

## What is learned

For every source currency, the fitter learns a histogram of `log(Amount Paid)` from
training rows. It records bin boundaries, counts, valid/invalid row counts, source
file digests, software versions and holdout metrics. The profile has its own digest.
The histogram model preserves a conditional marginal distribution; it does not
learn relationships among multiple numeric fields or transaction sequences.

The banking configuration explicitly maps USD/MXN/GBP/EUR/BRL to the reference's
currency names. This release has training data for all five. `missing_group=error`
prevents silent substitution. An explicit `preset` setting permits fallback, which
is then recorded in evidence. The profile is embedded in each generated run; later
integrity validation does not require the original reference or profile file.

Calibrated amounts replace the background amount/purpose/customer-segment presets
for covered currencies. Account activity, counterparties, currency mix, purposes,
timing, FX, fees and labels remain simulated. Optional AML motif amounts retain
their original rules and are outside the calibrated scope. The supplied calibrated
example disables AML to measure the amount model in isolation.

## Holdout and metrics

The default split assigns approximately 80% of rows to training and 20% to holdout
using a deterministic hash of row position and seed. Sorted file order and source
digests identify the input sequence. Two passes learn min/max from training only,
then count training and holdout against those same bin edges. This is independent
of batch boundaries, but is not an account-disjoint or chronological split.

`bin_total_variation` is half the sum of absolute differences between bin
probabilities: 0 means the same binned distribution and 1 means disjoint mass.
Values beyond training support are assigned to boundary bins for this calculation
and separately reported as `outside_training_support_fraction`. Constant-valued
groups are point masses. Low sample counts are flagged, not automatically accepted.

These diagnostics do not measure within-bin fidelity, temporal/network fidelity,
privacy, classifier performance or real-world AML detection. There is no global
"realism score" or automatic scientific acceptance threshold.

## Measured IBM pilot

The complete reference file yielded 15 fitted currency groups and no invalid rows
for the selected amount/currency columns. Reference holdout bin distances ranged
from 0.0053 to 0.0312. Three currency groups had a tiny fraction beyond training
support; this is recorded in the local report rather than hidden.

A 100,000-row banking baseline was compared before and after amount calibration,
using identical population settings and the frozen training histogram:

| Currency | Preset distance | Calibrated distance |
| --- | ---: | ---: |
| USD | 0.2401 | 0.0207 |
| MXN | 0.2521 | 0.0216 |
| GBP | 0.2340 | 0.0248 |
| EUR | 0.2193 | 0.0275 |
| BRL | 0.2944 | 0.0298 |

No generated amount in this pilot fell outside its training support. These are
sampling diagnostics for five amount distributions, not validation of the full
banking simulation. Whole-domain `empirically_calibrated` remains false; the evidence
records `amount_calibration.status=partial_reference_fit` and source origin.

## Limits and next work

- One numeric and one categorical field per profile; log or identity transforms.
- Bounded group count and batch processing; CSV decoder uses a bounded byte block.
- Invalid values are counted/excluded; malformed numeric text fails. Group labels
  must be categorical, not high-cardinality customer identifiers.
- No differential-privacy guarantee is provided for learned aggregates.
- Next fitting targets: payment formats, temporal behavior and account activity,
  then joint/network dependencies and independent fidelity experiments.

## Payment and source-clock profiling

Before applying temporal or payment patterns, inspect their joint distribution:

```bash
uv run --locked synthetic-engine profile-categories \
  --input data/references/ibm-aml/HI-Small_Trans.csv \
  --config configs/calibration/ibm-patterns.json \
  --output outputs/calibration/ibm-patterns/profile.json
```

This domain-independent command profiles configurable categories together with
source weekday/hour. It records daily volumes, weekday calendar exposure, invalid
rows and source/artifact hashes. Processing uses bounded batches and an explicit
joint-cell limit. CSV and Parquet inputs are supported. Raw reference data and
learned artifacts remain local.

This is a descriptive audit of the full source, not a held-out fitted model, and
does not change generated transactions. IBM source-clock timezone is unspecified;
hours cannot be interpreted as UTC or customer-local time. Calendar exposure is
inferred between observed endpoints, which may be partial; a short observed period
does not establish annual seasonality. Payment Format needs an explicit semantic
mapping before it can influence engine payment rails or purposes.

Measured IBM HI-Small audit: 5,078,345 valid rows, zero invalid rows,
15 currencies, seven payment formats and 12,351 occupied joint cells. Observed
source-clock range: 2022-09-01 00:00 through 2022-09-18 16:18. Weekday means
vary substantially (approximately 69,279 Sunday rows/day to 532,580 Thursday
rows/day); these are descriptive statistics of this short synthetic sample,
not a validated recurring schedule. Profile SHA256:
`dbd56424a32dd6869dd5d1acf525e00db4ae60d5c10fbc0965b4ee964ac4f93a`.

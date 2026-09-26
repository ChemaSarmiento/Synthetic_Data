# IBM payment-format mapping decision (CAL-010)

The [registered IBM source](ibm-hi-small.json) has seven Payment Format categories.
The current engine uses three rails selected from customer/purpose and cross-border
rules. These variables are not interchangeable. The machine-readable design is
[ibm-payment-mapping.json](../../configs/calibration/ibm-payment-mapping.json).

| IBM format | Candidate engine rail | Limitation |
| --- | --- | --- |
| ACH | bank_transfer | Coarser category; loses subtype |
| Credit Card | card | Does not establish POS channel or purchase purpose |
| Wire | wire | Does not establish cross-border status |
| Cheque | unsupported | No explicit rail in current model |
| Cash | unsupported | Needs explicit cash-event semantics |
| Reinvestment | unsupported | Needs investment-event semantics |
| Bitcoin | unsupported | Requires asset/network and amount-unit design |

Decision: report unsupported categories without silently dropping them or
renormalizing the remaining categories. Preserve a source payment-format field in
a future versioned banking schema before integrating a fitted categorical model.
Keep raw format, normalized rail, purpose and channel distinct. Current generation
remains unchanged. These mappings are engineering interpretations of category
labels and the existing code, not learned causal relationships.

## Small exploratory sample

```bash
uv run --locked python scripts/sample_ibm.py \
  --output outputs/samples/ibm-exploration-10k
```

The script selects exactly 10,000 rows using equal allocation across formats and
seeded bottom-k priorities within each format. It reads the CSV once, retaining
only bounded candidate buffers and five source columns plus row position. Source
hashing performs additional byte scans for integrity. Rare formats remain visible;
row weights N_h/n_h restore stratum population proportions. Unweighted sample
frequencies must not be reported as population estimates. Sampling does not
balance laundering labels or guarantee rare currency/hour/label combinations.

Only compact aggregate results should enter analysis context. The source and
sample remain ignored local artifacts. Future reuse reads this small Parquet,
not the full CSV. Sampling is exploratory and is not a train/test split.

Measured sample: 10,000 rows, all seven formats and 15 observed currencies.
Weighted coverage of the three candidate mappings is **41.27%** of source rows;
**58.73%** belongs to unsupported formats. Because format population totals determine
the weights, this coverage equals the registered population proportion; it is not
an independent estimate of mapping correctness. Extending the schema is necessary
before claiming representative IBM payment-format generation.

## Implemented schema extension (v0.4)

The mapping table above describes the original three-rail generator's limitations.
Payment schema v2 now represents all seven IBM formats in a separate reference
normalizer. Cheque/cash receive explicit rails, Bitcoin maps to crypto_transfer,
and reinvestment retains an unspecified rail. These are representational mappings,
not newly supported generative transaction mechanisms. The earlier 41.27% coverage
still describes candidate coverage of the existing simulation mechanisms.

```bash
uv run --locked python scripts/normalize_ibm_sample.py \
  --input outputs/samples/ibm-exploration-10k/sample.parquet \
  --output outputs/samples/ibm-payments-v2-10k
uv run --locked synthetic-engine generate \
  --config configs/banking/payments-v2.json \
  --output outputs/banking-payments-v2-10k
```

The normalizer retains source values and sample weights, adds explicit payment
semantics, and records input/output hashes. It accepts at most 10,000 rows. The
preset generator remains compatible: v2 is opt-in and appends fields without
changing existing values. Reference-origin metadata is excluded from model features.

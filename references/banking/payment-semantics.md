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

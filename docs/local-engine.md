# Local engine v0.1

## Run

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/synthetic-engine generate --config configs/banking-demo.json --output outputs/demo
.venv/bin/synthetic-engine validate outputs/demo
.venv/bin/synthetic-engine estimate outputs/demo --target-gb 15
.venv/bin/pytest -q
```

Choose a new output directory for each run. The engine refuses to overwrite existing paths, including failed runs. No cloud credentials are required; there are no network calls in generation.

## Output contract

```text
dimensions/                 banks, customers, accounts
transactions/event_date=…/  UTC-date partitioned Parquet, sorted by time
ground_truth/event_date=…/  matching IDs, labels and scenario metadata
summaries/                  account-level whole-window clustering features
manifest.json               configuration, versions, hashes, files, metrics, status
evidence.json               sources, assumptions and calibration limitations
schema.json                 transaction column types
model_features.json         candidate features and identifier exclusions
validation.json             integrity results and distribution diagnostics
progress.json               progress only; not a resumable state checkpoint
```

Use a single `transactions/` directory as the Parquet dataset root. Never scan all output subdirectories as one table: the dimension, label and summary schemas differ.

## Modeling

Transaction labels are keyed by `transaction_id` in `ground_truth/`. `scenario_motif` describes both benign controls and illicit scenarios; benign motifs do not imply laundering. All four motif families (fan-in, fan-out, chain, cycle) use four edges within an illustrative 90-minute interval. The requested prevalence is approximate: each day's scenario count is rounded down to complete four-edge motifs, with limited placement retries. The report contains actual prevalence.

`sender_prior_*` features contain only earlier events in `(timestamp, transaction_id)` order. They summarize history since the observation window began, not rolling 24-hour or 30-day windows. `-1` means no prior timestamp; zero means no historical mean, with `sender_history_available` to distinguish cold starts. Fees are charged separately in the sender's currency; received amount is the rounded conversion of principal. Every currency in this preset has two decimal minor units.

`known_related_party` assumes the relationship is known to the simulated bank; it is not inferred hidden ownership. Customers can own multiple accounts. Household and corporate groups are assigned within customer type and residence country. Transaction country denotes account/bank jurisdiction; in this pilot accounts are domestic to their owner's residence, and nationality is not modeled.

Start clustering with `summaries/account_summaries.parquet`, excluding account IDs and window timestamps from model inputs. These summaries use the **entire window**; never join them into earlier transaction predictions. Scale and encode using the training set only. For classification use chronological splits, a warm-up interval, and PR-AUC/precision-recall at the natural class prevalence. Scenario-network holdout and baseline model evaluation remain future work.

## Evidence and limitations

The preset is literature-informed and **not empirically calibrated**. Sources support the conceptual design, not the chosen numerical parameters. The machine-readable evidence profile is packaged at `src/synthetic_engine/evidence/banking-v1.json` and copied into every run. No IBM dataset has been downloaded or redistributed.

This pilot models five illustrative jurisdictions, heterogeneous bank categories, persistent counterparties, segment-dependent skewed amounts, weekday/payday volume variation, common ownership, and matched benign/illicit network motifs. Labels encode simulator intent. Legitimate motifs deliberately overlap illicit ones; neither easy classification nor real-world accuracy is promised.

Not yet implemented: empirical fitting, salary/bill recurrence per customer, complete industry/income profiles, realistic corridor calibration, DST/holiday calendars, account opening/closure during the window, balance conservation, settlement failure, rolling graph features, target-byte stopping, resumption, parallel generation, SQL/JSON adapters, cloud execution, and streaming. These are explicit next stages, not hidden capabilities of this pilot.

## Memory, size and reproducibility

The generator keeps account state and one day of rows in memory, then slices that day into output batches. `batch_rows` limits each file, not the full generation working set. `max_day_rows` enforces a daily safety bound; a run may reject a configuration whose weighted daily allocation exceeds it. Very large populations also increase memory. No full transaction dataset is held in RAM during validation.

The same configuration and dependency versions reproduce table contents. Changing output batch size preserves rows and labels, but changes file boundaries and hashes. Manifests record source checksums because a Git revision alone cannot identify uncommitted code. Runtime metrics vary. Interrupted runs remain incomplete and must be restarted in a new directory.

The 15 GB estimator extrapolates actual compressed Parquet bytes (all tables combined, decimal GB). It is a rough capacity measurement, not an executable 15 GB run or cloud price quote. Pilot file overhead and fixed dimensions distort scaling; benchmark larger batches and finalize the population before budgeting a large run.

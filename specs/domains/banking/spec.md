# BANK — Banking domain v0.2

Status: implemented. Banking baseline and AML pilots validated; all 64 AML Parquet file hashes match the retained v0.1 pilot with unchanged runtime dependencies. Reference calibration remains pending.

Banking is a domain of Synthetic Engine. It owns banks, customers, accounts,
relationships, transaction behavior, historical features and account summaries.
AML is an optional scenario configured independently; ordinary banking generation
must work with it disabled.

## Configuration and outputs

Domain ID: `banking`. Parameters: `accounts`, `banks`, `days`, `start_date`,
`max_day_rows`, and `scenarios`. The only current scenario key is `aml`.
Missing AML configuration defaults to disabled.

Tables: `dimensions/{banks,customers,accounts}.parquet`,
`transactions/event_date=…/*.parquet`, account summaries, and optional ground truth.
Existing transaction schema and mathematical assumptions remain as documented in
[the local guide](../../../docs/local-engine.md).

## Evidence and boundaries

The bundled profile is literature-informed, not empirically calibrated. Banks,
countries, activity weights, FX and temporal multipliers are simulated assumptions.
No reference dataset has been downloaded. Pending empirical calibration is a
separate milestone, not an outcome of modularization.

| ID | Acceptance criterion | Verification |
| --- | --- | --- |
| BANK-001 | Banking works without AML, labels or a target column | banking baseline test |
| BANK-002 | Preserve seeded v0.1 AML tables for identical settings and dependencies | comparison to retained pilot |
| BANK-003 | Enforce foreign keys, chronological order, FX and pre-event features | domain validator and replay tests |
| BANK-004 | Banking settings rejected independently of shared run settings | invalid banking config tests |

Population state and a daily partition reside in memory. This domain's time and
daily-size limits are not constraints on every future domain of the engine.

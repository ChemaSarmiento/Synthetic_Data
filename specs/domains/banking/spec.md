# BANK — Banking domain v0.3

Status: implemented. Banking baseline and AML pilots are validated. Optional v0.3 amount calibration is evaluated against IBM's synthetic reference; temporal and network calibration remain pending.

Banking is a domain of Synthetic Engine. It owns banks, customers, accounts,
relationships, transaction behavior, historical features and account summaries.
AML is an optional scenario configured independently; ordinary banking generation
must work with it disabled.

## Configuration and outputs

Domain ID: `banking`. Parameters: `accounts`, `banks`, `days`, `start_date`,
`max_day_rows`, `scenarios` and optional `amount_calibration`. The only current scenario key is `aml`.
Missing AML configuration defaults to disabled.

Tables: `dimensions/{banks,customers,accounts}.parquet`,
`transactions/event_date=…/*.parquet`, account summaries, and optional ground truth.
Existing transaction schema and mathematical assumptions remain as documented in
[the local guide](../../../docs/local-engine.md).

## Evidence and boundaries

The bundled profile is literature-informed, not empirically calibrated. Banks,
countries, activity weights, FX and temporal multipliers are simulated assumptions.
The optional calibration binding now fits background amounts to a locally acquired
IBM HI-Small file. It requires a profile path, explicit source-currency mapping and
missing-group behavior (`error` or `preset`). The default preset is unchanged.
This partial calibration is specified in [CAL](../../calibration/spec.md) and does
not establish full-domain fidelity.

| ID | Acceptance criterion | Verification |
| --- | --- | --- |
| BANK-001 | Banking works without AML, labels or a target column | banking baseline test |
| BANK-002 | Preserve seeded v0.1 AML tables for identical settings and dependencies | comparison to retained pilot |
| BANK-003 | Enforce foreign keys, chronological order, FX and pre-event features | domain validator and replay tests |
| BANK-004 | Banking settings rejected independently of shared run settings | invalid banking config tests |
| BANK-005 | Reference amounts use explicit units/mapping and remain verifiable without original source files | calibration binding integration test |

Population state and a daily partition reside in memory. This domain's time and
daily-size limits are not constraints on every future domain of the engine.

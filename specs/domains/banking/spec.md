# BANK — Banking domain v0.5

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

## BANK-PAY-002 — Opt-in payment schema v2

Status: implemented; payment distribution fitting remains pending (CAL-011).
`parameters.payment_schema_version` accepts integer 1 (default) or 2. V1 preserves
the existing event schema. V2 appends string fields:

| Field | Meaning |
| --- | --- |
| payment_format | Normalized instrument/event format, separate from rail |
| source_payment_format | Original reference label, or `not_applicable` for presets |
| payment_format_origin | `preset` or `reference:ibm-amlworld` |
| payment_mapping_status | Preset, direct, coarsened or rail_unknown |
| payment_asset_class | Fiat, crypto or unspecified; not a currency conversion |

Preset v2 generation derives `bank_transfer_unspecified`, `card_unspecified`, or
`wire` from existing rails without consuming randomness. It does not fabricate
ACH/credit-card detail from broader categories. All existing values and AML labels
remain unchanged for identical configurations/seeds. Validation enforces schema
version and preset field consistency. Source labels, origin and mapping status are
excluded from default model features to avoid encoding source provenance.

The separate IBM reference normalizer preserves all original columns, explicitly
represents cheque, cash and crypto_transfer rails, and leaves reinvestment's rail
unspecified. Purpose/channel remain unspecified rather than inferred from format.
Unknown labels and overwriting existing normalized fields fail. This adapter is
not a generated banking transaction dataset: no FX, cash counterparties, crypto
minor-unit arithmetic, investment lifecycle or timestamp interpretation is added.

Acceptance: old-column equality across v1/v2; batch invariance; all seven IBM
formats preserved; unknown labels rejected; no raw-column mutation; preset schema
inconsistency rejected; full v2 generation/validation pilot and feature exclusions.

## BANK-PAY-003 — Cheque and cash-mediated presets (v0.5)

Status: implemented, optional and **not reference fitted**. This extends the v0.4
representation with constrained event selection. It is not a settlement ledger.

`payment_mechanisms` accepts `cheque_probability` and `cash_probability`, both
finite numbers in [0,1], with sum <= 1. Missing values default to zero. Positive
values require `payment_schema_version=2`. A separate deterministic random stream
per day leaves the existing generator stream unchanged. A draw first chooses a
candidate format through disjoint intervals; ineligible candidates retain their
previous rail. Consequently configured probabilities are not final global shares.
No ground-truth label, motif or scenario field participates in selection.

| Mechanism | Eligible purpose | Channel | Interpretation |
| --- | --- | --- | --- |
| cheque | supplier_payment, salary, personal_transfer | branch | Abstract completed cheque transfer |
| cash | purchase, personal_transfer | in_person | Abstract cash-mediated transfer between modeled parties |

Both require same country/currency, distinct owners and distinct accounts. They
preserve principal amounts, timestamps, account relationships and existing truth;
FX is one, principal received equals principal paid, and assumed fees are zero.
These are explicit modeling constraints, not banking regulations or empirical
facts. No threshold-based amount limits or inferred customer risk are added.

Cash is not an ATM withdrawal or cash deposit: no separate cash wallet, teller,
deposit/withdrawal legs, denominations or cash-in-transit tracking exists. Cheques
have no issue/clearing timeline, bounced state or balance verification. Do not use
these mechanisms to claim settlement or balance-ledger realism. Amount calibration,
when enabled, remains conditional on currency, not payment format. Investment and
crypto generation remain unsupported.

Acceptance: default/zero setting compatibility; batch invariance; full probability
selects exactly eligible rows; invalid probabilities/schema combinations rejected;
independent stored-row validation rejects nonzero fees and disabled mechanisms;
AML truth and all unrelated values unchanged. Validator reports payment-rail counts.

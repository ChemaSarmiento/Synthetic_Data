# <ID> — <Domain name> v0.1

Status: draft

## Objective and users

What questions, tests or models will these datasets support? Define the domain
independently of optional anomaly, fraud or other scenarios.

## References and parameter provenance

For each source: URL/identifier, version/date, license, population, geography,
observation period, findings, parameters supported, uncertainty and limitations.
List measured parameters separately from assumed ones. Explain any extrapolation.

## Entity and behavior model

Entities, relationships, dependencies, distributions, time behavior, invariants
and optional scenarios. Avoid independent uniform draws unless justified.

## Configuration

Domain ID, typed `parameters`, defaults, valid ranges, resource bounds and
unknown-field handling. Reuse engine seed/rows/batch_rows; do not duplicate them.

## Output and feature contracts

Event-table name, partitions, Arrow schemas, keys/units/nullability, dimensions,
optional ground truth and summaries. Specify prediction time and feature leakage
constraints if classification is supported. Unlabelled domains are valid.

## Validation and acceptance

| ID | Criterion | Test / reference comparison | Status |
| --- | --- | --- | --- |
| <ID>-001 | Minimal deterministic generation | <test> | pending |
| <ID>-002 | Domain invariants | <test> | pending |
| <ID>-003 | Evidence and assumptions recorded | <test> | pending |
| <ID>-004 | Quantified reference fidelity, if calibrated | <report> | pending |

## Plan and tasks

Add `plan.md` for design choices and `tasks.md` for concrete implementation work.
Implement `Domain`, register a `DomainDefinition`, add package-data declarations
for evidence, provide a config and acceptance tests. Core orchestration must not
gain knowledge of domain entities. Add new shared capabilities only when needed.

## Limitations and next steps

State what is not modeled, supported scale, and evidence still required.

# Specification workflow

Synthetic Engine is the product. A domain supplies entities and behavior; a scenario
adds an optional use case inside that domain. Banking is the first domain and AML
is its first scenario. Neither is the definition of the engine.

Before implementation, write or amend the relevant specification:

1. State the use case, boundaries, source evidence and explicit assumptions.
2. Define the input configuration, output tables and invariants.
3. Assign acceptance criteria IDs and describe how each will be tested.
4. Record implementation decisions in `plan.md` and actionable work in `tasks.md`.
5. Implement the smallest vertical slice, run acceptance tests and a pilot.
6. Record evidence and limitations; update status and tasks when verified.

Statuses: **draft** (proposed), **implemented** (acceptance tests pass),
**validated-reference** (fidelity measured against a named, versioned source).
Implemented does not mean empirically realistic. Spec changes go through normal
Git review; this workflow does not add a separate approval requirement for local work.

## Specifications

- [Engine contract](engine/spec.md), [plan](engine/plan.md), [tasks](engine/tasks.md).
- [Banking domain](domains/banking/spec.md).
- [Optional AML scenario](domains/banking/aml/spec.md).
- [Reference calibration](calibration/spec.md), [plan](calibration/plan.md), [tasks](calibration/tasks.md).
- [New domain template](templates/domain.md).
- [Roadmap](../docs/roadmap.md).

This is a lightweight, repository-native start to specification-driven development,
not an integration with an external spec framework or automatic code generator.

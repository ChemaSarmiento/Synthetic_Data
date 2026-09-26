# AML — Optional banking scenario v0.2

Status: implemented. Banking baseline and AML pilots validated; all 64 AML Parquet file hashes match the retained v0.1 pilot with unchanged runtime dependencies. Reference calibration remains pending.

Scenario ID: `aml`, under the `banking` domain. This is a use case inside banking,
not a top-level engine domain or a requirement for other synthetic datasets.

Configuration: `enabled` (default false), `laundering_fraction` (default 0.001),
`legitimate_motif_fraction` (default 0.04). Fractions are simulation assumptions.

When enabled, inject fan-in, fan-out, chain and cycle motifs using the existing
four-edge, bounded-time algorithm. Include legitimate controls with overlapping
patterns. Export separate `transaction_id`, `is_laundering`, `scenario_id`, and
`scenario_motif` ground truth. Rounded daily counts determine actual prevalence.

When disabled, do not inject any AML/control motifs and do not export AML ground
truth or a classification target. All ordinary banking behavior remains available.

| ID | Acceptance criterion | Verification |
| --- | --- | --- |
| AML-001 | Four motif topologies and benign controls pass semantic validation | motif tests and domain validator |
| AML-002 | Labels and scenario identifiers excluded from event features | feature-contract tests |
| AML-003 | Disabled scenario exports no ground truth/target | baseline test |

References: IBM AMLSim parameter documentation, IBM AML-Data documentation and
the AMLworld paper. They support conceptual patterns, not the numeric presets.
No balance conservation or real-world AML effectiveness claim is made.

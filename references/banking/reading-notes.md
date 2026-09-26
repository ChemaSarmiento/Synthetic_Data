# Banking and AML research references

Reviewed 2026-09-26. These are original short notes, not copies of the papers.

## Primary benchmark: AMLworld / IBM AML-Data

Altman, Blanuša, von Niederhäusern, Egressy, Anghel and Atasu (NeurIPS 2023),
[Realistic Synthetic Financial Transactions for Anti-Money Laundering Models](https://arxiv.org/abs/2306.16424).

The paper describes an agent-based financial world and publishes transaction
benchmarks. It motivates preserving entities, relationships and behavior, rather
than generating independent rows. We use its IBM dataset as the first calibration
reference. Fitting our engine to this synthetic benchmark does not establish
agreement with actual customer records. Paper-era counts may differ from later
dataset releases; compute statistics from the exact downloaded file.

## AMLSim and graph structure

Weber et al. (2018), [Scalable Graph Learning for Anti-Money Laundering: A First Look](https://arxiv.org/abs/1812.00076).

This early work introduces scalable graph-learning experiments using AMLSim data.
It supports retaining transaction edges and graph context for AML research. AMLSim
is a separate simulator from AMLworld; its code and motifs must not be confused
with the selected IBM AMLworld benchmark. Our four-edge scenarios remain our own
documented approximations, not a reproduction of either simulator.

## Conditional synthetic generation and validation

Jensen et al. (Scientific Data 10, 661, 2023),
[A synthetic data set to benchmark anti-money laundering methods](https://doi.org/10.1038/s41597-023-02569-2).

SynthAML models alerts and associated transaction histories using a source from a
Danish bank. It motivates conditional modeling and evaluation across related
tables. Its alert outcomes are not interchangeable with transaction-level
laundering ground truth. We have not downloaded SynthAML or implemented its
copula method; it is a comparison and future-design reference.

## Unlabelled graph learning

Cardoso, Saleiro and Bizarro (2022),
[LaundroGraph: Self-Supervised Graph Representation Learning for Anti-Money Laundering](https://arxiv.org/abs/2210.14360).

LaundroGraph learns representations through a customer-transaction graph and a
self-supervised link-prediction task. It motivates supporting unlabelled datasets
and separate representation-learning experiments. It does not provide numeric
parameters for our generator or validate our simulation's realism.

## Decisions for the first calibration slice

- Fit payment amounts conditional on currency; never pool incomparable currencies.
- Use a training/holdout split and report fit limitations instead of claiming realism from a successful file export.
- Keep account relationships, timing, FX, scenarios and labels explicitly assumed until individually calibrated.
- Preserve source origin, release metadata, file size and SHA-256.
- Treat histogram binning and split settings as engineering choices, not numbers extracted from these papers.

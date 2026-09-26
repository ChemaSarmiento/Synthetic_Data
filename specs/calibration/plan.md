# Calibration implementation plan

1. Register IBM benchmark metadata and primary research papers; select one small file.
2. Implement shared CSV/Parquet readers, source hashing and split assignment.
3. Fit bounded conditional histograms and freeze training parameters before holdout evaluation.
4. Add CLI fitting and comparison commands; preserve source and model provenance.
5. Add optional banking amount binding and explicit currency fallback behavior.
6. Run acceptance tests and an IBM pilot. Record measured fidelity and remaining assumptions.

Reference files and learned artifacts stay in ignored `data/` and `outputs/`.
Only source metadata, original summaries, configuration and code are committed.

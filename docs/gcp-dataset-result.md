# AML dataset generation on GCP

Completed 2026-10-01 UTC. One Cloud Run Job execution produced a sharded dataset
in private Cloud Storage. Dataset index: `gs://<private-bucket>/datasets/<execution>/dataset.json`.
Access requires authorization to the bucket; no public objects are enabled.

## Measured result

| Measure | Result |
| --- | ---: |
| AML transaction rows | 109,000,000 |
| Transaction Parquet | 10,014,612,345 bytes (decimal), about 10.015 GB |
| All Parquet, including truth/dimensions/summaries | 10,796,042,454 bytes |
| Published objects | 7,631 |
| Independent shards | 109 |
| Positive laundering labels | 429,024 (about 0.394%) |
| Intentional laundering motif edges | 429,024 |
| Matched benign motif edges | 4,353,476 |
| Job execution | 4,682.13 seconds; 1h 18m 02s |
| Engine semantic checks | Passed separately in every shard |

The acceptance minimum was 10,000,000,000 transaction-only bytes; labels and
auxiliary Parquet do not count. The final shard crossed the target. The GCS audit
verified the full expected object inventory and object sizes, SHA256 of all shard
manifests and metadata, every shard's successful semantic validation report, and
the transaction-byte total. Each upload was checked against GCS server-reported
size and MD5. The audit did not redownload the 10 GB of transaction payloads.

## Generation design and caveats

The data uses the engine's documented, nonuniform literature-informed banking
presets. This cloud run did **not** apply the locally fitted IBM amount profile.
Banking populations, transaction behavior and AML labels are synthetic simulation
outputs; label intent is not independently verified real-world laundering.
Each shard contains one million rows, its own seed/population/account history and
AML motifs. IDs repeat between shards, so joins must include `shard_id`. Histories
and network motifs do not connect across shards. The 109 populations repeat the
same configured 30-day date window. Treating this as one continuous calendar or
single connected banking network would be incorrect.

Use the [dataset guide](gcp-dataset-use.md) for Spark reads and safe joins. GCS
lifecycle is set to delete dataset objects after 30 days and build-source objects
after 7 days. Change lifecycle before expiry if a longer retention is needed;
storage beyond that period has a charge.

Runtime list-price estimate, before account-level free usage/tax/local billing,
is approximately **US$0.12** for 4,682 seconds at 1 vCPU and 4 GiB under published
Cloud Run Jobs rates, plus build, retained image, storage and operations. The
owner-approved planning envelope was US$3. Billing export was not queried, so this
is not the actual invoiced amount. The monthly MXN400 budget is an alert, not a
hard cap.

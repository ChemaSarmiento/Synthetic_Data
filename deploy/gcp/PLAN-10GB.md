# AML GCP dataset: minimum 10 GB — approved 2026-09-30

2026-09-30. Supersedes the one-million-row execution scope in PLAN.md.
Owner approved this scope on 2026-09-30. Resources are provisioned and the single
bulk execution is in progress; completion awaits the final remote audit.

## Acceptance contract

At least **10,000,000,000 bytes (decimal GB)** of compressed transaction Parquet
objects stored privately in GCS. Ground truth, dimensions, summaries, metadata,
build sources and images do NOT count toward the minimum. This is a multipart
Parquet dataset, not a single giant file. The runner measures actual output bytes,
not a row-count extrapolation. It stops after the first validated and uploaded
shard that crosses the target, so size can exceed 10 GB by one shard.

Each shard contains one million transactions with an independent seed, population,
account history and AML topology. Composite keys are `(shard_id, transaction_id)`
and `(shard_id, account_id)` (similarly for banks, customers and scenarios). All
joins must include shard_id. There is no cross-shard graph/history continuity.
Use shard-aware train/test splits where relevant; random mixing does not validate
real-world transfer. The label expresses simulator intent, with matched benign
motif controls, not an externally verified customer-risk outcome.

Configuration: configs/gcp/aml-pilot.json,100000 accounts,100 banks,30-day windows,
AML nominal rate0.004, benign motif controls0.04. Current engine presets use
nonuniform literature-informed behavior. This run does NOT upload or apply the
local fitted IBM amount profile. Empirical full-domain fidelity is not claimed.

## Execution prepared

`deploy/gcp/run_bulk.py` runs sequentially in the existing container:
1. Generate and independently validate one complete shard in temporary scratch.
2. Upload all objects create-only; check server-reported size AND MD5 per object.
   SHA256 hashes remain in each shard manifest for subsequent verification.
3. Publish the shard manifest last, then remove that attempt's local scratch.
4. Accumulate only `transactions/` Parquet byte counts after successful uploads.
5. Publish root `dataset.json` only when the 10 GB acceptance condition is met.

Layout: `gs://BUCKET/datasets/EXECUTION/shard_id=0000/{transactions,ground_truth,...}`.
Transaction scan: `datasets/EXECUTION/shard_id=*/transactions/event_date=*/*.parquet`;
ground-truth scan uses the corresponding ground_truth path. Read Hive partitions
and retain shard_id. Do not read every Parquet file under the root as one table.
Read dataset.json to discover exactly the validated, published shard prefixes.

One task, no automatic retries. At most160 shards/160m rows; a3.5-hour internal
budget is checked between shards and a4-hour task timeout enforces the outer
limit. If the target cannot be reached, fail without a dataset completion marker.
Already uploaded shards remain individually validated; automatic resume is not
implemented. Do not launch additional paid retries without reassessing the cause.
No duplicate padding or fabricated file-size inflation is used to reach the target.

## Resources to approve

Region us-central1; exactly one build and one bulk execution:
- Enable Cloud Run, Cloud Build, Artifact Registry and IAM APIs.
- Private Standard Storage bucket `${PROJECT_ID}-aml-datasets`, uniform access and
  public access prevention. Disable soft delete for disposable staging/derived
  outputs. Lifecycle: build-source objects7days; datasets30days. Owner can retain
  data longer by changing lifecycle, with additional storage costs.
- Artifact Registry repository `synthetic-engine`, one built image.
- Keyless build and runtime service accounts as in PLAN.md. Runtime objectCreator
  scoped to the bucket; builder artifact writer on repository, source objectViewer
  on bucket and logging.logWriter on project. No owner/editor grants.
- Cloud Build standard e2-standard-2,600s timeout, dedicated builder, source staging
  inside the bucket. Source upload allowlist excludes local datasets and CHECKPOINT.
- Cloud Run Job `synthetic-aml-10gb`:1vCPU,4GiB RAM,1task,parallelism1,
  timeout14400s,max-retries0, runtime SA, OUTPUT_BUCKET environment variable.
  Override container command to `/app/.venv/bin/python /app/run_bulk.py`.
- No VM, Cloud SQL, scheduler, BigQuery queries, Pub/Sub or internet data export.

Scratch is bounded to one shard (~100MB Parquet plus generation/validation memory,
metadata and a <=64MiB upload buffer); no10GB memory allocation. Expected number of
shards roughly100–120, but compression and population affect it. Local timing is
not a guarantee of Cloud Run speed. Container build and real GCS access remain to
be verified in the approved execution.

## Cost estimate, not a hard cap

Official list pricing checked2026-09-30; do not assume free-tier availability:
- Cloud Run jobs1CPU/4GiB: (0.000018 +4*0.000002)*14400 = **US$0.3744**
  for a full4-hour task, before taxes/local currency pricing.
  https://cloud.google.com/run/pricing
- Cloud Build10min atUS$0.006/min: approximately **US$0.06**.
  https://cloud.google.com/build/pricing
- Plan for <=20GiB combined outputs/source storage at approximatelyUS$0.02/GiB-month,
  about **US$0.40** for30days, plus operations; actual measured sizes determine cost.
  https://cloud.google.com/storage/pricing
- Image storage assumption<=1GiB: roughly **US$0.10/month**, before allowances.
  https://cloud.google.com/artifact-registry/pricing
- Allow **US$3 total planning envelope** for this one build/execution,30-day small
  storage footprint, API operations and logs. This is a conservative estimate,
  NOT an enforced billing cap or a guarantee against unforeseen consumption.

Existing monthly budget: MXN400 alerts; not a hard stop. Actual MXN charges use
applicable GCP local SKUs/taxes. Downloading10GB to a local machine is out of scope
and can add network charges. Retaining images/data beyond the period also costs.

## Final verification/report

After execution, inspect job result and read root dataset.json. Verify the listed
shard manifests and GCS object metadata match their bytes/checksums. Report exact
transaction-only bytes, total rows, positive labels, shard count, GCS prefix,
validation status and measured runtime. Do not report completion from a partial
prefix, successful build, running job, row estimate or total bucket size alone.

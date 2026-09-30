# GCP AML pilot — pending owner approval

Prepared 2026-09-30. No cloud resources have been created for this plan.
Goal: test generation, validation and private upload in GCP before sizing 15 GB.

## Concrete scope

- Region: us-central1.
- Enable run.googleapis.com, cloudbuild.googleapis.com,
  artifactregistry.googleapis.com and iam.googleapis.com.
- One private Standard Storage bucket `${PROJECT_ID}-aml-pilot`, uniform bucket
  access, public access prevention; no public objects. Source bundles and output
  prefixes share the bucket. Retention cleanup after 7 days via lifecycle rules;
  explicitly disable soft delete for this disposable pilot to avoid extra retention.
- One Artifact Registry Docker repository `synthetic-engine` in the same region.
- Two keyless service accounts: `synthetic-pilot-runner` and `synthetic-pilot-build`.
  Runtime: bucket-scoped objectCreator only. Builder: repository-scoped writer,
  bucket-scoped objectViewer (for staged sources), project logging.logWriter.
  No owner/editor role grants, no service-account keys.
- Cloud Build: one Docker build, standard e2-standard-2 pool, 600-second timeout,
  explicit builder service account, source staging in the pilot bucket, logging only.
- Cloud Run Job `synthetic-aml-pilot`: 1 task, parallelism1, 1 vCPU, 2 GiB RAM,
  task timeout900s, max retries0, runner service account; no scheduler or endpoint.
- Exactly one manual execution after build/deployment. One million rows,100000
  accounts,100 banks,30 days, AML intent rate0.004 plus benign controls. Use the
  checked-in `configs/gcp/aml-pilot.json`. This infrastructure pilot uses documented
  presets, not the local learned IBM amount profile; no raw reference is uploaded.
- Output: partitioned Parquet transactions, separate AML truth, dimensions,
  summaries, evidence, validation, schemas and manifest under a unique execution
  prefix. Publish manifest last; an interrupted upload has no completion marker.

The container uses pinned Python/uv versions and locked project dependencies.
Source upload is an explicit allowlist. CHECKPOINT, credentials, local environment,
raw data, generated data and learned profiles are excluded. The runner obtains a
short-lived token from the metadata service; creates objects without overwrite.
Local scratch is memory-backed, so this runner refuses >1m rows. The later 15 GB
job needs a different disk/upload strategy; this is not that production runner.

## Cost estimate before free allowances, USD

Pricing checked on official pages 2026-09-30:
- Cloud Run Jobs: 0.000018/vCPU-second +0.000002/GiB-second in us-central1.
  At1 CPU/2GiB for900s: **$0.0198** for one timed-out task; usual pilot should
  finish sooner. https://cloud.google.com/run/pricing
- Build e2-standard-2: $0.006/minute;10min timeout budget approximately **$0.06**.
  https://cloud.google.com/build/pricing
- Artifact storage: approximately $0.10/GiB-month beyond free allowance;
  image <=1GiB planning assumption => $0.10/month until deleted.
  https://cloud.google.com/artifact-registry/pricing
- Standard single-region bucket storage, source objects, operations and small logs
  add a small amount. Estimate total pilot envelope **under US$1** for one build,
  one job and small retained artifacts; not a billing guarantee or hard cap.
  https://cloud.google.com/storage/pricing

Free-tier eligibility depends on account-wide consumption; do not promise zero
cost. Actual MXN billing uses applicable local SKUs/taxes, not an assumed exchange
rate. Existing monthly alert budget is MXN400 and is NOT a spending cap. No paid
managed SQL, BigQuery queries, Pub/Sub or internet dataset download is in scope.

## Execution after approval

1. Confirm resource-name availability and current billing; record approved scope
   in local CHECKPOINT. Create only the resources/permissions listed above.
2. Submit `deploy/gcp/cloudbuild.yaml` with `_IMAGE` set to the regional registry
   tag, using the dedicated builder and explicit source-staging bucket.
3. Deploy the job using the built image digest, explicit limits above and
   OUTPUT_BUCKET. Cloud Run supplies CLOUD_RUN_EXECUTION; no secrets in env vars.
4. Execute once, inspect task status/log summary, then read the output manifest and
   validation summary from Storage. Compare object inventory/sizes against manifest.
5. Report actual rows/bytes/runtime, AML counts and cost estimate. Propose the
   separate15GB design only after these measurements. Do not start it automatically.

Tests cover create-only object requests, size checks and manifest-last publication.
Container build, metadata authentication and actual GCS access remain unverified
until the approved cloud pilot runs. No claim of deployed success is made.

## Superseded execution scope

The user now requires at least10GB of transaction Parquet. See PLAN-10GB.md for
the current approval proposal and bulk runner; do not execute this smaller pilot
as fulfillment of the new size requirement.

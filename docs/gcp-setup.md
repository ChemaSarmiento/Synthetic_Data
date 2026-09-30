# Local GCP setup and deployment boundary

## Budget

Approved monthly budget: MXN 400, with 50/80/100% alerts. This is not a hard spending cap.
No cloud resources, billing links, APIs, service accounts, or budgets are to be created without first presenting the proposed changes and estimated costs to the owner.

Budget alerts do not enforce a spending cap. Before deployment, review billing-account-wide free-tier consumption, storage retention, compute, networking, image storage, query limits, and taxes where applicable. Do not assume a 15 GB dataset fits within free allowances.

## Local authentication

The Google Cloud CLI is installed outside this repository. Run in your own terminal:

```sh
gcloud auth login
gcloud projects list
```

Do not paste authorization codes, tokens, private keys, or credential JSON into Git or chat.
After selecting an existing project, use a dedicated local configuration:

```sh
gcloud config configurations create synthetic-data
gcloud config set account YOUR_GOOGLE_ACCOUNT
gcloud config set project YOUR_EXISTING_PROJECT_ID
```

If the configuration already exists, activate it instead of recreating it.
Application Default Credentials can be configured later when Python client libraries need them. CLI authentication alone is enough for the initial inventory.

## Read-only inventory after login

```sh
gcloud projects list
gcloud billing accounts list
gcloud billing projects describe YOUR_EXISTING_PROJECT_ID
gcloud services list --enabled --project YOUR_EXISTING_PROJECT_ID
```

These commands inspect existing resources. They do not provision infrastructure. Permissions may restrict results.

## Proposed deployment, not yet approved

- Cloud Run Jobs for bounded batch generation.
- Cloud Storage for Parquet and JSONL with a reviewed retention policy.
- BigQuery for bounded analytical samples.
- Local PostgreSQL initially; paid managed SQL only after cost review.
- Pub/Sub in a later streaming milestone.
- Terraform plans reviewed before any apply.

Official references:

- https://docs.cloud.google.com/sdk/docs/install-sdk
- https://docs.cloud.google.com/free/docs/free-cloud-features
- https://cloud.google.com/run/pricing
- https://docs.cloud.google.com/billing/docs/how-to/budgets

Concrete pilot proposal: [GCP AML pilot](../deploy/gcp/PLAN.md), pending owner approval.

Current requested target: [at least10GB of AML transaction Parquet](../deploy/gcp/PLAN-10GB.md).
This plan supersedes the smaller pilot and remains pending resource/cost approval.

# Using the sharded AML dataset

A bulk run is complete only when its GCS prefix contains `dataset.json` with
`status: complete` and `transaction_bytes >= 10000000000`. That count includes
compressed transaction Parquet only. Ground truth and auxiliary tables are extra.
The exact execution prefix and measured result are supplied after remote audit.

Each `shard_id=NNNN` is an independent synthetic population. Use composite keys:
`(shard_id, transaction_id)`, `(shard_id, account_id)`, and likewise for customers,
banks and scenarios. Joining by the numeric ID alone mixes unrelated populations.
Histories and graph edges are consistent within a shard, not across shards.

Read only the relevant table paths, preserving Hive partition columns. For Spark
with an already configured GCS connector and authorized identity:

```python
root = "gs://YOUR_BUCKET/datasets/YOUR_EXECUTION"
transactions = (spark.read.option("basePath", root)
    .parquet(f"{root}/shard_id=*/transactions/event_date=*/*.parquet"))
truth = (spark.read.option("basePath", root)
    .parquet(f"{root}/shard_id=*/ground_truth/event_date=*/*.parquet"))
classification = transactions.join(
    truth.select("shard_id", "transaction_id", "is_laundering"),
    ["shard_id", "transaction_id"], "inner")
```

Do not glob every Parquet under the root into one table: dimensions, summaries and
truth have different schemas. Restrict paths to the shards listed by the completed
dataset manifest. The cloud environment must supply credentials; never put tokens
or service-account keys into notebooks or the repository.

For clustering, start with transactions and the allowed features in each shard's
`model_features.json`. For classification, join only the target and keep identifiers,
scenario descriptions and provenance out of training features. Whole-window account
summaries leak future information into transaction-time prediction. Evaluate split
strategies explicitly; neither random row splits nor synthetic labels establish
real-world AML effectiveness. The preset includes matched legitimate motifs.

The approved bulk job uses documented nonuniform presets; it does not use the local
IBM-fitted amount profile. Data retention is30days under the approved bucket policy.
Exporting the entire dataset outside GCP can incur network charges and was not part
of the approved generation operation.

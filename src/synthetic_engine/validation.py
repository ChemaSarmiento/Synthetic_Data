"""Streaming integrity checks and diagnostics. Not a real-world fidelity score."""

from collections import Counter
import json
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from synthetic_engine.output import sha256


def require(condition, message):
    if not condition:
        raise ValueError(f"Validation failed: {message}")


def read(path):
    # ParquetFile avoids accidental hive partition type inference.
    return pq.ParquetFile(path).read()


def values(table, name):
    return table[name].combine_chunks().to_numpy(zero_copy_only=False)


def validate(root: Path):
    manifest = json.loads((root / "manifest.json").read_text())
    require(manifest["status"] in ("validating", "complete"), "run is incomplete")
    inventory = manifest["files"]
    expected = {f["path"] for f in inventory}
    actual = {str(p.relative_to(root)) for p in root.rglob("*.parquet")}
    require(expected == actual, "Parquet inventory differs from manifest")
    for item in inventory:
        path = root / item["path"]
        require(path.stat().st_size == item["bytes"] and sha256(path) == item["sha256"], f"file checksum {item['path']}")
        require(pq.ParquetFile(path).metadata.num_rows == item["rows"], "file row count")
    accounts = read(root / "dimensions/accounts.parquet")
    banks = read(root / "dimensions/banks.parquet")
    customers = read(root / "dimensions/customers.parquet")
    size = accounts.num_rows
    require(np.array_equal(values(accounts, "account_id"), np.arange(size)), "account IDs")
    account_bank = values(accounts, "bank_id")
    owner = values(accounts, "customer_id")
    require(np.all((account_bank >= 0) & (account_bank < banks.num_rows)), "bank foreign keys")
    require(np.all((owner >= 0) & (owner < customers.num_rows)), "customer foreign keys")
    country = values(accounts, "country")
    currency = values(accounts, "currency")
    group = values(customers, "relationship_group_id")[owner]
    opened = values(accounts, "opened_at").astype("datetime64[us]").astype(np.int64)
    out_count = np.zeros(size, dtype=np.int64)
    in_count = np.zeros(size, dtype=np.int64)
    out_sum = np.zeros(size)
    in_sum = np.zeros(size)
    observed_cross = np.zeros(size, dtype=np.int64)
    previous_timestamp = -1
    offset = 0
    positives = 0
    cross_count = 0
    country_counts = Counter()
    purpose_counts = Counter()
    motif_counts = Counter()
    per_day = Counter()
    sampled_amounts = []
    stride = max(1, manifest["config"]["rows"] // 50_000)
    scenario_edges = {}
    current_partition = None

    def check_scenarios():
        for sid, edges in scenario_edges.items():
            require(len(edges) == 4, f"scenario {sid} has incomplete edges")
            kind = edges[0][2]
            require(all(e[2:] == edges[0][2:] for e in edges), "scenario labels disagree")
            a, b = [e[0] for e in edges], [e[1] for e in edges]
            if kind == "fan_in":
                good = len(set(a)) == 4 and len(set(b)) == 1
            elif kind == "fan_out":
                good = len(set(a)) == 1 and len(set(b)) == 4
            elif kind == "chain":
                good = a[1:] == b[:-1] and len(set(a + b)) == 5
            elif kind == "cycle":
                good = a[1:] == b[:-1] and b[-1] == a[0] and len(set(a)) == 4
            else:
                good = False
            require(good, f"invalid topology in scenario {sid}")
            motif_counts[("illicit_" if edges[0][3] else "legitimate_") + kind] += 1
        scenario_edges.clear()

    for item in inventory:
        if not item["path"].startswith("transactions/"):
            continue
        relative = item["path"]
        partition = relative.split("/")[1]
        if current_partition != partition:
            check_scenarios()
            current_partition = partition
        tx = read(root / relative)
        truth = read(root / relative.replace("transactions/", "ground_truth/", 1))
        n = tx.num_rows
        require(all(col.null_count == 0 for col in tx.columns), "unexpected nulls")
        for field in tx.schema:
            if pa.types.is_floating(field.type):
                require(np.all(np.isfinite(values(tx, field.name))), f"nonfinite {field.name}")
        require(not {"is_laundering", "scenario_id", "scenario_motif"} & set(tx.column_names), "ground-truth leakage")
        ids = values(tx, "transaction_id")
        require(np.array_equal(ids, np.arange(offset, offset + n)), "transaction ID ordering")
        require(np.array_equal(ids, values(truth, "transaction_id")), "ground truth alignment")
        ts = values(tx, "timestamp").astype("datetime64[us]").astype(np.int64)
        expected_day = np.datetime64(partition.split("=", 1)[1], "D")
        require(np.all(ts.astype("datetime64[us]").astype("datetime64[D]") == expected_day), "date partition")
        require(np.all(ts[1:] >= ts[:-1]) and ts[0] >= previous_timestamp, "chronological order")
        previous_timestamp = int(ts[-1])
        src, dst = values(tx, "sender_account_id"), values(tx, "receiver_account_id")
        require(np.all((src >= 0) & (src < size) & (dst >= 0) & (dst < size)), "account foreign keys")
        require(np.all(src != dst), "self transfers")
        require(np.all(opened[src] <= ts) and np.all(opened[dst] <= ts), "account opening dates")
        for side, accounts_ix in (("sender", src), ("receiver", dst)):
            require(np.array_equal(values(tx, side + "_bank_id"), account_bank[accounts_ix]), "account/bank consistency")
            require(np.array_equal(values(tx, side + "_country"), country[accounts_ix]), "account/country consistency")
        require(np.array_equal(values(tx, "payment_currency"), currency[src]), "sender currency")
        require(np.array_equal(values(tx, "receiving_currency"), currency[dst]), "receiver currency")
        require(np.array_equal(values(tx, "same_owner"), owner[src] == owner[dst]), "ownership relationship")
        require(np.array_equal(values(tx, "known_related_party"), group[src] == group[dst]), "known relationship")
        amount = values(tx, "amount_paid_minor")
        received = values(tx, "amount_received_minor")
        fx = values(tx, "fx_rate")
        require(np.all(amount > 0) and np.all(received > 0) and np.all(np.isfinite(fx)), "positive finite amounts/FX")
        require(np.array_equal(received, np.maximum(1, np.rint(amount * fx)).astype(np.int64)), "FX rounding")
        usd = values(tx, "amount_usd_equivalent")
        require(np.all(np.isfinite(usd) & (usd > 0)), "USD equivalents")
        historical_count = values(tx, "sender_prior_out_count")
        historical_in = values(tx, "sender_prior_in_count")
        historical_mean = values(tx, "sender_prior_mean_usd")
        # Replay independently from persisted rows to catch current/future leakage.
        for i, (a, b, amount_usd) in enumerate(zip(src, dst, usd)):
            require(historical_count[i] == out_count[a], "historical outgoing count")
            require(historical_in[i] == in_count[a], "historical incoming count")
            expected_mean = out_sum[a] / out_count[a] if out_count[a] else 0
            require(abs(historical_mean[i] - expected_mean) <= 1e-7 * max(1, expected_mean), "historical mean includes future data")
            out_count[a] += 1
            in_count[b] += 1
            out_sum[a] += amount_usd
            in_sum[b] += amount_usd
        labels = values(truth, "is_laundering")
        scenarios = values(truth, "scenario_id")
        motifs = values(truth, "scenario_motif")
        require(np.all(~labels | (scenarios >= 0)), "positive label without scenario")
        require(np.all((scenarios >= 0) == (motifs != "none")), "scenario metadata")
        for i in np.flatnonzero(scenarios >= 0):
            scenario_edges.setdefault(int(scenarios[i]), []).append((int(src[i]), int(dst[i]), str(motifs[i]), bool(labels[i])))
        cross = country[src] != country[dst]
        require(np.array_equal(cross, values(tx, "is_cross_border")), "cross-border flag")
        np.add.at(observed_cross, src, cross.astype(np.int64))
        positives += int(labels.sum())
        cross_count += int(cross.sum())
        per_day[partition] += n
        country_counts.update(values(tx, "sender_country").tolist())
        purpose_counts.update(values(tx, "purpose").tolist())
        sampled_amounts.extend(usd[ids % stride == 0].tolist())
        offset += n
    check_scenarios()
    require(offset == manifest["config"]["rows"], "total requested rows")
    summary = read(root / "summaries/account_summaries.parquet")
    require(np.array_equal(values(summary, "account_id"), np.arange(size)), "summary account IDs")
    require(np.array_equal(values(summary, "out_count"), out_count), "summary outgoing counts")
    require(np.array_equal(values(summary, "in_count"), in_count), "summary incoming counts")
    require(np.allclose(values(summary, "out_usd"), out_sum), "summary outgoing amounts")
    require(np.allclose(values(summary, "in_usd"), in_sum), "summary incoming amounts")
    expected_cross_share = np.divide(observed_cross, out_count, out=np.zeros(size), where=out_count > 0)
    require(np.allclose(values(summary, "cross_border_share"), expected_cross_share), "summary cross-border share")
    return {
        "passed": True, "rows": offset, "laundering_rows": positives,
        "laundering_fraction": positives / offset, "cross_border_fraction": cross_count / offset,
        "amount_usd_quantiles": dict(zip(["p50", "p90", "p99"], np.quantile(sampled_amounts, [0.5, 0.9, 0.99]).tolist())),
        "quantile_method": "deterministic transaction-ID stride sample, at most about 100k rows",
        "sender_country_counts": dict(country_counts), "purpose_counts": dict(purpose_counts),
        "scenario_counts": dict(motif_counts), "daily_rows": dict(per_day),
        "checks": ["checksums", "row counts", "foreign keys", "chronology", "FX", "relationships", "ground truth separation", "historical count/mean replay", "scenario topology", "account summary reconciliation"],
        "limitations": ["No empirical reference comparison", "No balance ledger validation", "Not a guarantee of downstream model generalization"],
    }

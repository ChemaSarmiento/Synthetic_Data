"""Banking pilot: fixed entities, skewed activity, temporal variation, graph motifs.

All numerical distributions are explicit simulation assumptions. No empirical
calibration is claimed. Memory is bounded by population size plus one day.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from importlib.resources import files
import json
import numpy as np
import pyarrow as pa

from synthetic_engine.config import Config
from synthetic_engine.core import Batch
from synthetic_engine.domains.banking.config import BankingConfig
from synthetic_engine.domains.banking.calibration import BankingAmountModel
from synthetic_engine.domains.banking.scenarios.aml import inject, apply_amount_patterns

COUNTRIES = np.array(["US", "MX", "GB", "DE", "BR"])
CURRENCIES = np.array(["USD", "MXN", "GBP", "EUR", "BRL"])
TIMEZONES = ["America/New_York", "America/Mexico_City", "Europe/London", "Europe/Berlin", "America/Sao_Paulo"]
FX = np.array([1.0, 18.0, 0.8, 0.92, 5.0])  # Illustrative, NOT historical quotes.
BANK_TYPES = np.array(["retail", "commercial", "private", "digital", "cooperative"])


class BankingDomain:
    def __init__(self, config: Config):
        self.config = c = BankingConfig.from_run(config)
        rng = np.random.default_rng(np.random.SeedSequence([c.seed, 0]))
        self.start = datetime.combine(date.fromisoformat(c.start_date), datetime.min.time(), timezone.utc)
        self.start_us = int(self.start.timestamp() * 1_000_000)
        self.offsets = np.array([self.start.astimezone(ZoneInfo(z)).utcoffset().total_seconds() / 3600 for z in TIMEZONES])
        self.bank_country = np.arange(c.banks) % len(COUNTRIES)
        self.bank_type = rng.permutation(np.arange(c.banks)) % len(BANK_TYPES)
        bank_weight = rng.lognormal(0, 1.1, c.banks)
        # Two accounts per customer allow same-owner transfers without identity leakage.
        self.owner = np.arange(c.accounts) // 2
        customer_count = int(self.owner[-1]) + 1
        self.customer_business = rng.random(customer_count) < 0.24
        self.customer_business[:2] = [False, True]
        self.customer_country = rng.choice(5, customer_count, p=[0.35, 0.25, 0.15, 0.15, 0.10])
        self.business = self.customer_business[self.owner]
        self.bank = np.zeros(c.accounts, dtype=np.int64)
        for country in range(5):
            bank_pool = np.flatnonzero(self.bank_country == country)
            ix = np.flatnonzero(self.customer_country[self.owner] == country)
            probabilities = bank_weight[bank_pool] / bank_weight[bank_pool].sum()
            self.bank[ix] = rng.choice(bank_pool, len(ix), p=probabilities)
        self.country = self.bank_country[self.bank]
        self.amount_model = (BankingAmountModel(c.amount_calibration, CURRENCIES[np.unique(self.country)])
                             if c.amount_calibration is not None else None)
        self.customer_group = np.zeros(customer_count, dtype=np.int64)
        group_offset = 0
        for country in range(5):
            for business in (False, True):
                members = np.flatnonzero((self.customer_country == country) & (self.customer_business == business))
                self.customer_group[members] = group_offset + np.arange(len(members)) // 3
                group_offset += (len(members) + 2) // 3
        self.group = self.customer_group[self.owner]
        self.activity = rng.lognormal(0, 1.1, c.accounts) * np.where(self.business, 3.5, 1.0)
        self.amount_scale = rng.lognormal(np.where(self.business, 7.3, 4.5), 0.7)
        self.open_age_days = rng.integers(30, 3650, c.accounts)
        self.preferred = rng.integers(0, c.accounts, (c.accounts, 4))
        self.country_accounts = [np.flatnonzero(self.country == i) for i in range(len(COUNTRIES))]
        for country, pool in enumerate(self.country_accounts):
            if not len(pool):
                continue
            local = rng.random((len(pool), 4)) < 0.9
            local_choices = rng.choice(pool, local.shape)
            self.preferred[pool] = np.where(local, local_choices, self.preferred[pool])
        for j in range(4):
            same = self.preferred[:, j] == np.arange(c.accounts)
            self.preferred[same, j] = (self.preferred[same, j] + 1) % c.accounts
        self.out_count = np.zeros(c.accounts, dtype=np.int64)
        self.in_count = np.zeros(c.accounts, dtype=np.int64)
        self.out_sum = np.zeros(c.accounts)
        self.in_sum = np.zeros(c.accounts)
        self.out_m2 = np.zeros(c.accounts)
        self.last_out = np.full(c.accounts, -1, dtype=np.int64)
        self.last_in = np.full(c.accounts, -1, dtype=np.int64)
        self.cross_count = np.zeros(c.accounts, dtype=np.int64)
        self.observed_days = np.zeros(c.accounts, dtype=np.int64)
        self.day_last_active = np.full(c.accounts, -1, dtype=np.int64)
        dates = [self.start.date() + timedelta(days=i) for i in range(c.days)]
        weights = np.array([(0.55 if d.weekday() >= 5 else 1.0) * (1.35 if d.day in (1, 15, 28, 29, 30, 31) else 1.0) for d in dates])
        self.day_counts = rng.multinomial(c.rows, weights / weights.sum())
        if self.day_counts.max() > c.max_day_rows:
            raise ValueError("A weighted daily partition exceeds max_day_rows; reduce rows or increase days")
        self.scenario_counter = 0

    def dimensions(self):
        c = self.config
        customers = len(self.customer_business)
        return {
            "banks": pa.table({
                "bank_id": np.arange(c.banks, dtype=np.int32),
                "country": COUNTRIES[self.bank_country],
                "bank_type": BANK_TYPES[self.bank_type],
            }),
            "customers": pa.table({
                "customer_id": np.arange(customers),
                "customer_type": np.where(self.customer_business, "business", "individual"),
                "residence_country": COUNTRIES[self.customer_country],
                "relationship_group_id": self.customer_group,
                "group_type": np.where(self.customer_business, "corporate_group", "household"),
            }),
            "accounts": pa.table({
                "account_id": np.arange(c.accounts), "customer_id": self.owner,
                "bank_id": self.bank.astype(np.int32), "country": COUNTRIES[self.country],
                "currency": CURRENCIES[self.country],
                "account_type": np.where(self.business, "business_current", "personal_current"),
                "opened_at": pa.array(self.start_us - self.open_age_days * 86_400_000_000, type=pa.timestamp("us", tz="UTC")),
            }),
        }

    def _day(self, day, n):
        c = self.config
        rng = np.random.default_rng(np.random.SeedSequence([c.seed, 1, day]))
        day_date = self.start.date() + timedelta(days=day)
        weight = self.activity * np.where(self.business & (day_date.weekday() >= 5), 0.35, 1.0)
        src = rng.choice(c.accounts, n, p=weight / weight.sum())
        dst = rng.integers(0, c.accounts, n)
        # Mostly domestic corridors, persistent relationships, and common ownership.
        domestic = rng.random(n) < 0.8
        for country, pool in enumerate(self.country_accounts):
            ix = np.flatnonzero(domestic & (self.country[src] == country))
            if len(ix):
                dst[ix] = rng.choice(pool, len(ix))
        familiar = rng.random(n) < 0.5
        dst[familiar] = self.preferred[src[familiar], rng.integers(0, 4, familiar.sum())]
        own = rng.random(n) < 0.06
        dst[own] = src[own] ^ 1
        dst[dst >= c.accounts] = 0
        same = dst == src
        dst[same] = (dst[same] + 1) % c.accounts
        local_hour = np.where(self.business[src], rng.normal(13, 3, n), rng.normal(17, 5, n)) % 24
        utc_hour = (local_hour - self.offsets[self.country[src]]) % 24
        ts = self.start_us + day * 86_400_000_000 + (utc_hour * 3_600_000_000).astype(np.int64)
        order = np.argsort(ts, kind="stable")
        ts, src, dst = ts[order], src[order], dst[order]
        label, scenario, typology, motif_sets, self.scenario_counter = inject(
            rng, src, dst, ts, c.accounts, c.aml, self.scenario_counter)
        # Purposes and rails are selected after motifs, so neither exposes labels.
        business = self.business[src]
        purpose = np.where(business, "supplier_payment", "purchase").astype("U24")
        personal_transfer = (~business) & (rng.random(n) < 0.35)
        purpose[personal_transfer] = "personal_transfer"
        salary = business & (~self.business[dst]) & np.isin(day_date.day, [1, 15, 28, 29, 30, 31])
        purpose[salary] = "salary"
        purpose[self.owner[src] == self.owner[dst]] = "own_account_transfer"
        cross = self.country[src] != self.country[dst]
        rail = np.where(business, "bank_transfer", "card").astype("U20")
        rail[purpose != "purchase"] = "bank_transfer"
        rail[cross] = "wire"
        channel = np.where(rail == "card", "pos", "online").astype("U12")
        channel[(rail != "card") & (rng.random(n) < 0.35)] = "mobile"
        amount = rng.lognormal(np.log(self.amount_scale[src]), 0.9)
        amount[salary] = rng.lognormal(7.2, 0.4, salary.sum())
        if self.amount_model is not None:
            eligible = np.ones(n, dtype=bool)
            for positions in motif_sets:
                eligible[positions] = False
            self.amount_model.apply(amount, self.country[src], CURRENCIES, FX, eligible, rng)
        apply_amount_patterns(amount, motif_sets, rng)
        maximum_minor = np.max(amount * FX[self.country[src]] * 100)
        if not np.all(np.isfinite(amount)) or maximum_minor >= 2**63 - 1:
            raise ValueError("Generated amount exceeds finite int64 minor-unit representation")
        paid = np.maximum(1, np.rint(amount * FX[self.country[src]] * 100)).astype(np.int64)
        usd = paid / (100 * FX[self.country[src]])
        rate = FX[self.country[dst]] / FX[self.country[src]]
        received = np.maximum(1, np.rint(paid * rate)).astype(np.int64)
        fee = np.rint(paid * np.where(cross, 0.002, 0.0001)).astype(np.int64)
        return ts, src, dst, label, scenario, typology, purpose, rail, channel, paid, usd, rate, received, fee

    def _features(self, day, ts, src, dst, usd):
        n = len(src)
        count = np.empty(n, dtype=np.int64)
        incount = np.empty(n, dtype=np.int64)
        mean = np.empty(n)
        std = np.empty(n)
        last_out = np.empty(n)
        last_in = np.empty(n)
        ratio = np.empty(n)
        for i, (t, a, b, amount) in enumerate(zip(ts, src, dst, usd)):
            k = self.out_count[a]
            count[i], incount[i] = k, self.in_count[a]
            mean[i] = self.out_sum[a] / k if k else 0
            std[i] = np.sqrt(self.out_m2[a] / (k - 1)) if k > 1 else 0
            last_out[i] = (t - self.last_out[a]) / 1e6 if self.last_out[a] >= 0 else -1
            last_in[i] = (t - self.last_in[a]) / 1e6 if self.last_in[a] >= 0 else -1
            ratio[i] = self.in_sum[a] / (self.out_sum[a] + 1)
            # Update after recording pre-event features (also for incoming activity).
            self.out_count[a] += 1
            self.out_sum[a] += amount
            self.out_m2[a] += (amount - mean[i]) * (amount - self.out_sum[a] / (k + 1))
            self.in_count[b] += 1
            self.in_sum[b] += amount
            self.last_out[a], self.last_in[b] = t, t
            self.cross_count[a] += self.country[a] != self.country[b]
            for account in (a, b):
                if self.day_last_active[account] != day:
                    self.observed_days[account] += 1
                    self.day_last_active[account] = day
        return {
            "sender_prior_out_count": count, "sender_prior_in_count": incount,
            "sender_prior_mean_usd": mean, "sender_prior_std_usd": std,
            "sender_seconds_since_out": last_out, "sender_seconds_since_in": last_in,
            "sender_prior_in_out_ratio": ratio,
            "amount_to_prior_mean": np.divide(usd, mean, out=np.zeros(n), where=mean > 0),
            "sender_history_available": count > 0,
        }

    def batches(self):
        offset = 0
        c = self.config
        for day, n in enumerate(self.day_counts):
            if not n:
                continue
            ts, src, dst, label, scenario, typology, purpose, rail, channel, paid, usd, rate, received, fee = self._day(day, int(n))
            features = self._features(day, ts, src, dst, usd)
            local_hour = ((ts / 3_600_000_000 + self.offsets[self.country[src]]) % 24).astype(np.int8)
            day_date = self.start.date() + timedelta(days=day)
            events = pa.table({
                "transaction_id": np.arange(offset, offset + n),
                "timestamp": pa.array(ts, type=pa.timestamp("us", tz="UTC")),
                "sender_account_id": src, "receiver_account_id": dst,
                "sender_bank_id": self.bank[src].astype(np.int32), "receiver_bank_id": self.bank[dst].astype(np.int32),
                "sender_country": COUNTRIES[self.country[src]], "receiver_country": COUNTRIES[self.country[dst]],
                "sender_bank_type": BANK_TYPES[self.bank_type[self.bank[src]]],
                "receiver_bank_type": BANK_TYPES[self.bank_type[self.bank[dst]]],
                "sender_customer_type": np.where(self.business[src], "business", "individual"),
                "receiver_customer_type": np.where(self.business[dst], "business", "individual"),
                "payment_currency": CURRENCIES[self.country[src]], "receiving_currency": CURRENCIES[self.country[dst]],
                "amount_paid_minor": paid, "amount_received_minor": received,
                "amount_usd_equivalent": usd, "fx_rate": rate, "fee_paid_minor": fee,
                "payment_rail": rail, "purpose": purpose, "channel": channel,
                "is_cross_border": self.country[src] != self.country[dst],
                "same_bank": self.bank[src] == self.bank[dst],
                "same_owner": self.owner[src] == self.owner[dst],
                "known_related_party": self.group[src] == self.group[dst],
                "sender_account_age_days": self.open_age_days[src] + day,
                "sender_local_hour": local_hour, "utc_weekday": np.full(n, day_date.weekday(), dtype=np.int8),
                "is_utc_weekend": np.full(n, day_date.weekday() >= 5),
                **features,
            })
            truth = pa.table({
                "transaction_id": np.arange(offset, offset + n), "is_laundering": label,
                "scenario_id": scenario, "scenario_motif": typology,
            })
            for begin in range(0, int(n), c.batch_rows):
                yield Batch(day_date.isoformat(), events.slice(begin, c.batch_rows), truth.slice(begin, c.batch_rows) if c.aml.enabled else None)
            offset += int(n)

    def summaries(self):
        c = self.config
        mean = np.divide(self.out_sum, self.out_count, out=np.zeros(c.accounts), where=self.out_count > 0)
        return {"account_summaries": pa.table({
            "account_id": np.arange(c.accounts),
            "window_start": pa.array([self.start] * c.accounts, type=pa.timestamp("us", tz="UTC")),
            "window_end_exclusive": pa.array([self.start + timedelta(days=c.days)] * c.accounts, type=pa.timestamp("us", tz="UTC")),
            "out_count": self.out_count, "in_count": self.in_count,
            "out_usd": self.out_sum, "in_usd": self.in_sum, "mean_out_usd": mean,
            "cross_border_share": np.divide(self.cross_count, self.out_count, out=np.zeros(c.accounts), where=self.out_count > 0),
            "active_days": self.observed_days,
        })}

    def evidence(self):
        profile = json.loads(files("synthetic_engine.domains.banking").joinpath("evidence.json").read_text())
        profile["active_scenarios"] = ["aml"] if self.config.aml.enabled else []
        if self.amount_model is not None:
            profile["amount_calibration"] = self.amount_model.evidence()
            profile["mode"] = "partially_reference_fitted"
            # Whole-domain fidelity is still unverified even when one parameter is fitted.
            profile["empirically_calibrated"] = False
            profile["sources"].append(self.amount_model.profile["fit_config"]["source"])
        return profile

    def model_features(self, schema):
        excluded = {"transaction_id", "timestamp", "sender_account_id", "receiver_account_id", "sender_bank_id", "receiver_bank_id"}
        return {
            "features": [name for name in schema.names if name not in excluded],
            "excluded_identifiers": sorted(excluded),
            "target": "ground_truth.is_laundering" if self.config.aml.enabled else None,
            "notes": "Fit encoding/scaling on training data only. Chronological split required. Do not join whole-window summaries into transaction prediction features.",
        }

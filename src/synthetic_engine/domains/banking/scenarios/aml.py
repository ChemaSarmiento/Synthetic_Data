"""Optional AML injection and topology validation, with matched benign controls."""

from collections import Counter
from dataclasses import dataclass
import numpy as np

from synthetic_engine.checks import require

MOTIFS = np.array(["fan_in", "fan_out", "chain", "cycle"])


@dataclass(frozen=True)
class AMLConfig:
    enabled: bool = False
    laundering_fraction: float = 0.001
    legitimate_motif_fraction: float = 0.04

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError("aml.enabled must be boolean")
        for key in ("laundering_fraction", "legitimate_motif_fraction"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 0.2:
                raise ValueError(f"{key} must be between 0 and 0.2")


def inject(rng, src, dst, ts, accounts, config: AMLConfig, counter):
    n = len(src)
    label = np.zeros(n, dtype=bool)
    scenario = np.full(n, -1, dtype=np.int64)
    typology = np.full(n, "none", dtype="U16")
    # Match legitimate and illicit motifs in structure and amount distribution.
    # Their labels encode simulator intent, not an observable decision rule.
    used = np.zeros(n, dtype=bool)
    motif_sets = []
    if not config.enabled:
        return label, scenario, typology, motif_sets, counter
    for illicit, fraction in ((True, config.laundering_fraction), (False, config.legitimate_motif_fraction)):
        count = int(n * fraction / 4)
        for _ in range(count):
            if n < 4:
                break
            positions = None
            for attempt in range(20):
                first = int(rng.integers(0, n - 3))
                end = int(np.searchsorted(ts, ts[first] + 90 * 60 * 1_000_000, side="right"))
                available = np.flatnonzero(~used[first:end]) + first
                if len(available) >= 4:
                    positions = np.sort(rng.choice(available, 4, replace=False))
                    break
            if positions is None:
                continue
            nodes = rng.choice(accounts, 5, replace=False)
            kind = counter % 4
            if kind == 0:
                a, b = nodes[1:], np.repeat(nodes[0], 4)
            elif kind == 1:
                a, b = np.repeat(nodes[0], 4), nodes[1:]
            elif kind == 2:
                a, b = nodes[:-1], nodes[1:]
            else:
                a, b = nodes[:4], np.roll(nodes[:4], -1)
            src[positions], dst[positions] = a, b
            used[positions] = True
            label[positions] = illicit
            scenario[positions] = counter
            typology[positions] = MOTIFS[kind]
            motif_sets.append(positions)
            counter += 1
    return label, scenario, typology, motif_sets, counter


def apply_amount_patterns(amount, positions, rng):
    for ix in positions:
        base = rng.lognormal(6.0, 0.85)
        amount[ix] = base * rng.uniform(0.96, 1.04, 4)


def validate_topology(scenario_edges):
    motif_counts = Counter()
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

    return motif_counts

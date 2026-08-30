"""Anonymity-set size of the per-transaction construction fingerprint, at survey scale.

The N-S sparsity premise is that most records have no close neighbours in feature space.
This measures the opposite quantity directly: for each transaction, how many other
transactions share its exact fingerprint vector. Two vector widths are compared (12 axes
vs 19) to test whether more dimensions actually buy distinctiveness, and two scopes
(whole window vs single epoch) because the class a vector falls into depends on how much
chain the observer aggregates.

Scope: this is a per-TRANSACTION vector. It says nothing about the distinctiveness of a
cluster's feature DISTRIBUTION, which needs a clustering and is measured elsewhere.

usage: python3 examples/fingerprint_sparsity.py <epochs.jsonl>
"""
import json
import sys
from collections import Counter

LABELS = ["exactly 1", "2-9", "10-99", "100-999", "1,000-9,999",
          "10,000-99,999", ">=100,000"]


def bucket(size):
    if size == 1:
        return LABELS[0]
    for i, hi in enumerate((10, 100, 1_000, 10_000, 100_000), start=1):
        if size < hi:
            return LABELS[i]
    return LABELS[-1]


def distribution(counts):
    """counts: vector -> occurrences. Returns bucket -> share of TRANSACTIONS (not vectors)
    landing in a class of that size, so the reading is "a transaction's own crowd"."""
    out = Counter()
    for size in counts.values():
        out[bucket(size)] += size
    total = sum(out.values())
    return {label: out.get(label, 0) / total for label in LABELS}, total


def render(name, dist, total):
    print(f"\n{name}  (n={total:,})")
    for label in LABELS:
        share = dist[label]
        print(f"  {label:>16}  {share * 100:6.3f}%  {'#' * round(share * 60)}")


def main(path):
    window, extended = Counter(), Counter()
    per_epoch = []
    epochs = 0
    for line in open(path):
        d = json.loads(line)
        v12, v19 = d["vectors"], d["vectors_extended"]
        window.update(v12)
        extended.update(v19)
        per_epoch.append(distribution(v12)[0])
        epochs += 1
    print(f"epochs: {epochs}  txs: {sum(window.values()):,}")

    d12, n12 = distribution(window)
    render("12-axis vector, whole window", d12, n12)
    d19, n19 = distribution(extended)
    render("19-axis vector, whole window", d19, n19)

    med = {label: sorted(e[label] for e in per_epoch)[len(per_epoch) // 2]
           for label in LABELS}
    render("12-axis vector, median single epoch", med, n12 // epochs)

    lt10 = lambda d: d["exactly 1"] + d["2-9"]
    lt100 = lambda d: lt10(d) + d["10-99"]
    print(f"\nshare in a class < 10:   12-axis {lt10(d12) * 100:.3f}%   "
          f"19-axis {lt10(d19) * 100:.3f}%   single epoch {lt10(med) * 100:.3f}%")
    print(f"share in a class < 100:  12-axis {lt100(d12) * 100:.3f}%   "
          f"19-axis {lt100(d19) * 100:.3f}%   single epoch {lt100(med) * 100:.3f}%")


if __name__ == "__main__":
    main(sys.argv[1])

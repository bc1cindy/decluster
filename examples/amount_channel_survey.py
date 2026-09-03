"""What each arm of the amount channel actually says on a real slice.

The channel has four arms and, until now, no measurement of how often any of them speaks on real
transactions: the coinjoin de-mix, the unnecessary-input heuristic, the 2-in/2-out sub-transaction
re-partition, and the subset-sum multiplicity W(E). Each is refuse-only, so what matters is the
*abstention rate* — an arm that never fires cannot be carrying the weight its prose implies.

Needs an export with prevout values and script types; the graph-scale exports carry neither.

usage: python3 examples/amount_channel_survey.py <slice.ndjson|.json> [max_txs]
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster import views
from decluster.coinjoin_demix import coinjoin_demix
from decluster.conservation import forced_in_round
from decluster.counting import guaranteed_log_w, w_total
from decluster.extractors import x_uih
from decluster.monitor import is_coinjoin
from decluster.subtransaction import subtransactions


def load(path, cap):
    """Read either NDJSON or a JSON array, coercing the numeric fields some exports stringify."""
    raw = open(path).read().lstrip()
    rows = json.loads(raw) if raw.startswith("[") else [
        json.loads(line) for line in raw.splitlines() if line.strip()]

    def num(x):
        return int(x) if x is not None else None

    out = []
    for tx in rows[:cap]:
        if tx.get("height") is not None:
            tx["height"] = num(tx["height"])
        for v in tx.get("vin") or []:
            p = v.get("prevout") or {}
            if p.get("value") is not None:
                p["value"] = num(p["value"])
        for o in tx.get("vout") or []:
            if o.get("value") is not None:
                o["value"] = num(o["value"])
        out.append(tx)
    return out


def complete(tx):
    """Whether the amount channel can read this transaction at all."""
    vin = tx.get("vin") or []
    return bool(vin) and all((v.get("prevout") or {}).get("value") is not None for v in vin) \
        and all(o.get("value") is not None for o in tx.get("vout") or [])


def main(path, cap=10 ** 9):
    txs = load(path, cap)
    usable = [t for t in txs if complete(t)]
    multi = [t for t in usable if len(t["vin"]) >= 2]
    print(f"{path}: {len(txs):,} txs, {len(usable):,} with complete amounts, "
          f"{len(multi):,} multi-input", flush=True)

    demixed = shape = 0
    for tx in multi:
        if is_coinjoin(tx):
            shape += 1
        if views._demix_participants(tx) is not None:
            demixed += 1
    print(f"\ncoinjoin detector fires on {shape:,} ({shape / len(multi):.3%} of multi-input)")
    print(f"de-mix resolves >=2 participants on {demixed:,} "
          f"({demixed / len(multi):.3%}) — the arm's real contribution to refusal")

    uih = Counter(x_uih(t) for t in multi)
    fires = len(multi) - uih.get("none", 0)
    print(f"\nunnecessary-input heuristic fires on {fires:,} ({fires / len(multi):.2%})")

    two = [t for t in usable if len(t["vin"]) == 2 and len(t.get("vout") or []) == 2]
    decided = amb = 0
    for tx in two:
        ranked, bits = subtransactions(tx)
        if not ranked:
            continue
        decided += 1
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            amb += 1                      # top two equally round: the re-partition does not decide
    print(f"\n2-in/2-out transactions: {len(two):,}; the re-partition ranks {decided:,} of them, "
          f"and {amb:,} ({amb / decided if decided else 0:.2%}) tie at the top")

    kinds = Counter()
    guaranteed = 0
    for tx in multi[:2000]:
        res = w_total([v["prevout"]["value"] for v in tx["vin"]],
                      [o["value"] for o in tx["vout"]])
        kinds[str(res.get("kind"))] += 1
        if guaranteed_log_w(res) is not None:
            guaranteed += 1
    counted = sum(kinds.values())
    print(f"\nsubset-sum W(E) over {counted:,} multi-input transactions:")
    for kind, n in kinds.most_common():
        print(f"  {kind:>12}: {n:>6,}  {n / counted:>7.2%}")
    print(f"  usable as a lower bound (exact or lower-bound tier): {guaranteed:,} "
          f"({guaranteed / counted:.2%})")

    forced_any = 0
    for tx in multi[:2000]:
        largest = max(v["prevout"]["value"] for v in tx["vin"])
        if forced_in_round(tx, largest):
            forced_any += 1
    print(f"\nconservation forces at least one output value on {forced_any:,} of "
          f"{min(len(multi), 2000):,} multi-input transactions, taking the largest input as the "
          f"known participant ({forced_any / min(len(multi), 2000):.2%})")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9)

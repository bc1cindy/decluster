"""Canonical fingerprint-pair validation: does the library model separate same-wallet tx pairs
(address-reuse label) from random pairs? Scores pairs with LibraryScorer over all library axes
and reports AUC. Offline."""
import random
from .graph_deanon import auc


def _input_addrs(tx):
    return {a for v in tx["vin"] if (a := (v.get("prevout") or {}).get("scriptpubkey_address"))}


def reuse_pairs(txs, cap=4000, seed=0):
    """Same-owner label = address reuse. positives = sampled pairs of distinct txs sharing an input
    address; negatives = sampled random distinct-tx pairs. Returns (positives, negatives) as lists of
    (txA, txB). Bounded and deterministic under seed."""
    rng = random.Random(seed)
    by_addr = {}
    for tx in txs:
        for a in _input_addrs(tx):
            by_addr.setdefault(a, {})[tx["txid"]] = tx      # dedup txs per address by txid
    groups = [list(g.values()) for g in by_addr.values() if len(g) >= 2]
    pos = []
    while len(pos) < cap and groups:
        a, b = rng.sample(rng.choice(groups), 2)
        pos.append((a, b))
    neg, n = [], len(txs)
    while len(neg) < cap and n >= 2:
        i, j = rng.randrange(n), rng.randrange(n)
        if txs[i]["txid"] != txs[j]["txid"]:
            neg.append((txs[i], txs[j]))
    return pos, neg


def evaluate(txs, combiner, cap=4000, seed=0):
    """Score positives/negatives with combiner.score and return separation metrics. shuffle_auc flips
    each aligned pair's label -> expect ~0.5."""
    pos_pairs, neg_pairs = reuse_pairs(txs, cap, seed)
    pos = [combiner.score(a, b) for a, b in pos_pairs]
    neg = [combiner.score(a, b) for a, b in neg_pairs]
    rng = random.Random(seed)
    spos, sneg = [], []
    for p, ng in zip(pos, neg):
        if rng.random() < 0.5: spos.append(p); sneg.append(ng)
        else: spos.append(ng); sneg.append(p)
    return {"n_pos": len(pos), "n_neg": len(neg),
            "pos_mean": (sum(pos) / len(pos)) if pos else None,
            "neg_mean": (sum(neg) / len(neg)) if neg else None,
            "auc": auc(pos, neg, seed), "shuffle_auc": auc(spos, sneg, seed)}


class LibraryScorer:
    """Canonical Fellegi-Sunter pair scorer over ALL library axes (library.AXES) — the witness-bearing
    multi-axis model, using the corrected extractors. Agreement on a value adds its measured library
    bits; a mismatch adds a clamped (<=0) weight; 0-bit/absent values are skipped. Replaces the deleted
    rust_bridge vector scorer with the canonical extractor path."""
    def __init__(self, consistency=0.95, floor_n=1000):
        from . import extractors, engine, library
        self.c = consistency
        self.floor_n = floor_n
        self.axes = []
        for a in library.AXES:
            fn = getattr(extractors, a["extractor"], None) or getattr(engine, a["extractor"], None)
            if fn is None:
                continue
            p = {v: 2 ** -b for v, b in (a.get("bits") or {}).items() if b > 0}
            if a["axis"] == "locktime":
                # locktime_class emits a bare "height" bucket offline (no block_height), so fold the
                # library's height_* sub-classes into it; "zero" and "timestamp" are emitted as-is.
                h = sum(pv for v, pv in p.items() if v.startswith("height"))
                p = {v: pv for v, pv in p.items() if not v.startswith("height")}
                if h:
                    p["height"] = h
            if not p:
                continue
            self.axes.append((a["axis"], fn, p, sum(pv * pv for pv in p.values())))

    def score(self, txA, txB, explain=False):
        import math
        total, rows = 0.0, []
        for name, fn, p, collision in self.axes:
            va, vb = fn(txA), fn(txB)
            if va not in p and vb not in p:                          # both abstain/absent -> skip
                rows.append((name, va, vb, None)); continue
            if va == vb:
                w = -math.log2(p.get(va, 1.0 / self.floor_n))        # measured library bits
            else:
                w = min(0.0, math.log2((1 - self.c) / max(1 - collision, 1e-6)))
            total += w; rows.append((name, va, vb, w))
        return (total, rows) if explain else total


def load_blkcache(path=".blkcache"):
    """Witness-bearing txs from the local mempool block-tx cache. Dedup by txid; skip non-tx entries.
    Offline (reads local JSON files)."""
    import glob, json, os
    seen, out = set(), []
    for f in sorted(glob.glob(os.path.join(path, "*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for tx in (d if isinstance(d, list) else [d]):
            if not isinstance(tx, dict) or not tx.get("vin"):
                continue
            if any(v.get("is_coinbase") or v.get("prevout") is None for v in tx["vin"]):
                continue                                    # coinbase / uncached input -> incomplete
            tid = tx.get("txid")
            if tid in seen:
                continue
            seen.add(tid); out.append(tx)
    return out

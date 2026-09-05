"""Canonical fingerprint-pair validation: does the library model separate same-wallet tx pairs
(address-reuse label) from random pairs? Scores pairs with LibraryScorer over all library axes
and reports AUC. Offline."""
import random
from .graph_deanon import auc, shuffle_auc
from .rarity_weight_baseline import rarity_score
from .change_gt import input_addrs


def reuse_pairs(txs, cap=4000, seed=0):
    """Same-owner label = address reuse. positives = sampled pairs of distinct txs sharing an input
    address; negatives = sampled random distinct-tx pairs. Returns (positives, negatives) as lists of
    (txA, txB). Bounded and deterministic under seed."""
    rng = random.Random(seed)
    by_addr = {}
    for tx in txs:
        for a in sorted(input_addrs(tx)):                   # sorted -> group order is PYTHONHASHSEED-independent
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


def evaluate(txs, scorer, cap=4000, seed=0):
    """Score positives/negatives with scorer.score and return separation metrics. shuffle_auc flips
    each aligned pair's label -> expect ~0.5."""
    pos_pairs, neg_pairs = reuse_pairs(txs, cap, seed)
    pos = [scorer.score(a, b) for a, b in pos_pairs]
    neg = [scorer.score(a, b) for a, b in neg_pairs]
    return {"n_pos": len(pos), "n_neg": len(neg),
            "pos_mean": (sum(pos) / len(pos)) if pos else None,
            "neg_mean": (sum(neg) / len(neg)) if neg else None,
            "auc": auc(pos, neg, seed), "shuffle_auc": shuffle_auc(pos, neg, seed)}


# Correlated axis clusters measured on the cache (`fs_ablation.dependent_clusters`, |phi| >= 0.6
# within either class) with the representative each one keeps (`fs_ablation.group_ablation`: the
# member carrying the largest |agreement_weight| in the train-fitted model). The additive rarity
# kernel has no conditional-independence correction, so within a cluster it scores one fact
# several times; keeping a single representative is the decorrelated reading of the same evidence.
AXIS_CLUSTERS = (
    (("input_script_type", "input_types_present", "nested_segwit", "pubkey_compression",
      "sighash"), "input_script_type"),
    (("change_index", "change_matches_output", "change_type_match"), "change_index"),
    (("input_order", "io_shape", "output_order"), "io_shape"),
    (("change_spk", "output_encoding"), "change_spk"),
)

REDUNDANT_AXES = frozenset(
    axis for cluster, keep in AXIS_CLUSTERS for axis in cluster if axis != keep)

# Axes the shared input address fixes outright. The same-owner label is that shared address, so
# agreement on these is partly the label restating itself rather than construction style.
ADDRESS_DETERMINED_AXES = frozenset({
    "input_script_type", "input_types_present", "nested_segwit", "pubkey_compression",
    "change_address_reuse",
})


class LibraryScorer:
    """Legacy rarity pair scorer over the measured fingerprint axes.

    `drop` excludes named axes before scoring. The default drops nothing and is what every
    published number uses; `decorrelated_scorer` and `construction_only_scorer` are the two named
    variants, kept alongside rather than replacing it."""
    def __init__(self, consistency=0.95, floor_n=1000, drop=()):
        from . import extractors, engine, library
        self.c = consistency
        self.floor_n = floor_n
        self.axes = []
        drop = frozenset(drop)
        for a in library.AXES:
            if a["axis"] in drop:
                continue
            fn = getattr(extractors, a["extractor"], None) or getattr(engine, a["extractor"], None)
            if fn is None:
                continue
            p = library.p_from_bits(a.get("bits"))
            if a["axis"] == "locktime":
                # locktime_class emits a bare "height" bucket offline; fold the height_* sub-classes
                # into it; "zero" and "timestamp" are emitted as-is.
                h = sum(pv for v, pv in p.items() if v.startswith("height"))
                p = {v: pv for v, pv in p.items() if not v.startswith("height")}
                if h:
                    p["height"] = h
            if not p:
                continue
            collision = sum(pv * pv for pv in p.values())
            abstain = (lambda va, vb, p=p: va not in p and vb not in p)
            self.axes.append((a["axis"], fn, p, collision, abstain))

    def score(self, txA, txB, explain=False):
        return rarity_score(self.axes, txA, txB, self.c, self.floor_n, explain)


def decorrelated_scorer(consistency=0.95, floor_n=1000):
    """One representative per correlated cluster: 14 axes rather than 23."""
    return LibraryScorer(consistency, floor_n, drop=REDUNDANT_AXES)


def construction_only_scorer(consistency=0.95, floor_n=1000):
    """Only the axes the shared-input-address label does not determine: 18 axes rather than 23.
    Separates construction style from the label restating itself."""
    return LibraryScorer(consistency, floor_n, drop=ADDRESS_DETERMINED_AXES)


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

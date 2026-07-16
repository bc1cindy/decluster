"""Special-case change labels (Ron & Shamir): near-certain change identification from a single
signal, used as an INDEPENDENT label to validate fingerprints non-circularly. label_optimal_change
reads ONLY values — disjoint from co-spend/addresses AND from ordering/nSequence/version — which is
what breaks the circularity that invalidates cluster findNext against an M&N co-spend label."""
from .change_gt import is_candidate, input_addrs, out_addr

def label_optimal_change(tx):
    """Optimal-change / UIH: in a >=2-input 2-output tx, the output smaller than the smallest input
    value MUST be change (else an input was unnecessary). Returns that index when exactly one output
    qualifies, else None. Reads ONLY values."""
    if not is_candidate(tx): return None
    iv = [v.get("prevout", {}).get("value") for v in tx["vin"]]
    if any(v is None for v in iv) or len(iv) < 2: return None
    ov = [o.get("value") for o in tx["vout"]]
    if any(v is None for v in ov): return None
    smin = min(iv)
    small = [i for i in (0, 1) if ov[i] < smin]
    return small[0] if len(small) == 1 else None

def label_address_reuse(tx):
    """Address reuse (self-change): the single output whose address is an input address. NOTE: reuse
    is itself a clustering signal, so this does NOT break the findNext circularity — it only
    cross-checks the per-axis test. Returns that index, else None."""
    if not is_candidate(tx): return None
    ia = input_addrs(tx)
    reused = [i for i in (0, 1) if out_addr(tx, i) in ia]
    return reused[0] if len(reused) == 1 else None

def build_gt_special(txs, labeler):
    gt = []
    for tx in txs:
        ci = labeler(tx)
        if ci is not None:
            gt.append({"tx": tx, "change_index": ci})
    return gt

from .extractors import _change_index

# Within-tx which-output predictors: round_number (less-round output is change) and address_reuse
# (output reusing an input address). Position and type-match are excluded: position requires a
# cluster's change-index habit; type-match only qualifies the round-number pick, not an output.
WITHIN_TX = {"round_number": _change_index, "address_reuse": label_address_reuse}

def within_tx_rates(gt, preds=WITHIN_TX):
    """{name: (tpr, fpr, coverage)} of each within-tx predictor vs the special-case label. TP: pred
    == label; FP: pred == the other (spend) output. Denominator = len(gt)."""
    n = len(gt) or 1
    out = {}
    for name, fn in preds.items():
        tp = fp = cov = 0
        for rec in gt:
            v = fn(rec["tx"])
            if v is None: continue
            cov += 1
            if v == rec["change_index"]: tp += 1
            else: fp += 1
        out[name] = (tp / n, fp / n, cov / n)
    return out

def label_agreement(gt_a, gt_b):
    """Over transactions labeled by BOTH gts (keyed by txid), agreement/disagreement of the change
    index. Returns {"both", "agree", "disagree", "only_a", "only_b"}."""
    a = {r["tx"]["txid"]: r["change_index"] for r in gt_a}
    b = {r["tx"]["txid"]: r["change_index"] for r in gt_b}
    both = a.keys() & b.keys()
    agree = sum(1 for t in both if a[t] == b[t])
    return {"both": len(both), "agree": agree, "disagree": len(both) - agree,
            "only_a": len(a.keys() - b.keys()), "only_b": len(b.keys() - a.keys())}

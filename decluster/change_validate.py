"""Validation metrics over a labeled slice: per-axis TPR/FPR (M&N Table 4), combined pre<->post AUC,
a shuffle null control (the net that caught the temporal fingerprint), and the universal baseline.
Pure functions with injected fetchers; the slice pipeline (change_slice) drives them."""
import random
from .fetch import fetch_tx, fetch_outspends
from .combiner import Combiner
from .change_score import output_score, spending_tx
from .graph_deanon import auc
from .extractors import x_input_order, x_output_order, x_nsequence, x_version, x_change_index

AXES = {"input_order": x_input_order, "output_order": x_output_order,
        "nsequence": x_nsequence, "version": x_version}

def axis_vote(tx, axis_fn, get_tx=fetch_tx, get_outspends=fetch_outspends):
    """M&N consistent-fingerprint vote: the output whose spending tx matches T on this axis,
    when exactly one output does. Else None."""
    va = axis_fn(tx)
    matches = []
    for i in (0, 1):
        post = spending_tx(tx, i, get_tx, get_outspends)
        if post is not None and axis_fn(post) == va:
            matches.append(i)
    return matches[0] if len(matches) == 1 else None

def per_axis_rates(gt, get_tx=fetch_tx, get_outspends=fetch_outspends):
    """axis -> (tpr, fpr, coverage) over GT. TP: vote == change label; FP: vote == spend.
    Denominator = len(gt) (M&N: over ground-truth txs)."""
    n = len(gt) or 1
    out = {}
    for name, fn in AXES.items():
        tp = fp = cov = 0
        for rec in gt:
            v = axis_vote(rec["tx"], fn, get_tx, get_outspends)
            if v is None: continue
            cov += 1
            if v == rec["change_index"]: tp += 1
            else: fp += 1
        out[name] = (tp / n, fp / n, cov / n)
    return out

def universal_baseline_rates(gt):
    """The intra-tx baseline the pre<->post scorer must beat: the universal 'less-round output =
    change' heuristic (x_change_index), computed with no forward-walk. Returns (tpr, fpr, cov)."""
    n = len(gt) or 1
    tp = fp = cov = 0
    for rec in gt:
        v = x_change_index(rec["tx"])
        if v not in ("first", "last"): continue
        idx = 0 if v == "first" else 1
        cov += 1
        if idx == rec["change_index"]: tp += 1
        else: fp += 1
    return (tp / n, fp / n, cov / n)

def combined_auc(gt, combiner, get_tx=fetch_tx, get_outspends=fetch_outspends, seed=0):
    """AUC that the change output's onward-spend agreement exceeds the spend output's, over txs
    where BOTH outputs are spent. Shuffle control randomizes the label per pair -> expect ~0.5."""
    pos, neg = [], []
    for rec in gt:
        s0 = output_score(rec["tx"], 0, combiner, get_tx, get_outspends)
        s1 = output_score(rec["tx"], 1, combiner, get_tx, get_outspends)
        if s0 is None or s1 is None: continue
        ci = rec["change_index"]
        pos.append(s0 if ci == 0 else s1)
        neg.append(s1 if ci == 0 else s0)
    rng = random.Random(seed)
    spos, sneg = [], []
    for p, ng in zip(pos, neg):
        if rng.random() < 0.5: spos.append(p); sneg.append(ng)
        else: spos.append(ng); sneg.append(p)
    return {"auc": auc(pos, neg, seed), "shuffle_auc": auc(spos, sneg, seed), "n_paired": len(pos)}

def report(gt, combiner=None, get_tx=fetch_tx, get_outspends=fetch_outspends):
    combiner = combiner or Combiner.from_library()
    lines = [f"# GT change-id validation  (n={len(gt)})", "",
             "%-14s %6s %6s %8s" % ("axis", "TPR", "FPR", "coverage")]
    for name, (tpr, fpr, cov) in per_axis_rates(gt, get_tx, get_outspends).items():
        lines.append("%-14s %6.3f %6.3f %8.3f" % (name, tpr, fpr, cov))
    bt, bf, bc = universal_baseline_rates(gt)
    lines.append("%-14s %6.3f %6.3f %8.3f  (universal baseline)" % ("change_index", bt, bf, bc))
    c = combined_auc(gt, combiner, get_tx, get_outspends)
    lines += ["", "combined pre<->post scorer:",
              "  AUC=%s  shuffle_AUC=%s  n_paired=%d" % (c["auc"], c["shuffle_auc"], c["n_paired"]),
              "",
              "note: per-axis input_order is the raw M&N 'Ordered ins/outs' universal heuristic;",
              "the combined AUC uses the FS Combiner, which abstains on single/small_n order.",
              "the two input_order views are not directly comparable."]
    return "\n".join(lines)


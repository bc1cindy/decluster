"""Regime test: are wallet fingerprints sparse quasi-identifiers or equivalence-class
conditioners? Compares the N-S fingerprint channel (overlap + eccentricity gap) with the
F-S combiner on the same reuse-pairs, over three rarity sources. Offline.
Run from repo root: .venv/bin/python examples/fingerprint_ns.py. See results/RESULTS-fingerprint-regime.md."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decluster import fingerprint_ns as fns
from decluster.fingerprint_validate import load_blkcache, reuse_pairs, LibraryScorer
from decluster.change_gt import input_addrs
from decluster.graph_deanon import auc


def build_labeled_nodes(txs, cap=200, seed=0):
    """One owner_id per address-reuse group; each node a tx (deterministic, order-stable).
    A tx whose inputs reuse more than one address is assigned to exactly one owner - the
    first qualifying group in sorted-address order - so a txid never appears twice."""
    by_addr = {}
    for tx in txs:
        for a in sorted(input_addrs(tx)):
            by_addr.setdefault(a, {})[tx["txid"]] = tx
    nodes, assigned, owner = [], set(), 0
    for addr, g in sorted(by_addr.items()):
        members = [tx for txid, tx in sorted(g.items()) if txid not in assigned]
        if len(members) < 2:
            continue
        for tx in members:
            assigned.add(tx["txid"])
            nodes.append((tx, owner))
        owner += 1
        if len(nodes) >= cap:
            break
    return nodes[:cap]


def run_regime(txs, weights, label):
    axis_fns = fns.axis_fns()
    scorer = LibraryScorer()
    pos, neg = reuse_pairs(txs, cap=2000, seed=0)

    ns_auc = fns.pairwise_auc(pos, neg, axis_fns, weights)
    fs_auc = auc([scorer.score(a, b) for a, b in pos],
                 [scorer.score(a, b) for a, b in neg], 0)

    nodes = build_labeled_nodes(txs)
    within_gaps, ns_correct, fs_correct, n = [], 0, 0, 0
    for i, (q, owner) in enumerate(nodes):
        others = [(t, o) for j, (t, o) in enumerate(nodes) if j != i]
        if not others:
            continue
        cand_txs = [t for t, _ in others]
        r = fns.reid_gap(q, cand_txs, axis_fns, weights)
        n += 1
        if r["best"] is not None and others[r["best"]][1] == owner:
            ns_correct += 1
        # F-S top-1 on the same candidate set
        fs_scores = [scorer.score(q, t) for t in cand_txs]
        fs_best = max(range(len(fs_scores)), key=lambda k: fs_scores[k])
        if others[fs_best][1] == owner:
            fs_correct += 1
        # within-class gap: candidates sharing q's equivalence key
        qk = fns.equivalence_key(q, axis_fns)
        wc = [t for t in cand_txs if fns.equivalence_key(t, axis_fns) == qk]
        if len(wc) >= 2:
            within_gaps.append(fns.reid_gap(q, wc, axis_fns, weights)["gap"])

    return {"label": label, "ns_auc": ns_auc, "fs_auc": fs_auc,
            "ns_top1": ns_correct / n if n else 0.0, "fs_top1": fs_correct / n if n else 0.0,
            "within_gap_mean": (sum(within_gaps) / len(within_gaps)) if within_gaps else 0.0,
            "within_n": len(within_gaps)}


def main():
    txs = load_blkcache()
    axis_fns = fns.axis_fns()
    lib = fns.library_weights()
    sources = [("library", lib),
               ("measured", fns.measured_weights(txs, axis_fns))]
    lumen_path = os.environ.get("LUMEN_PRIOR")
    have_lumen = bool(lumen_path) and os.path.exists(lumen_path)
    if have_lumen:
        sources.append(("lumen", fns.lumen_weights(lumen_path, lib)))
    print("# Fingerprint regime test on %d txs\n" % len(txs))
    if not have_lumen:
        print("# lumen source skipped: no prior given (set LUMEN_PRIOR to a prior JSON path)\n")
    print("%-10s %8s %8s %9s %9s %13s" % ("source", "NS_AUC", "FS_AUC", "NS_top1", "FS_top1", "within_gap"))
    for label, w in sources:
        r = run_regime(txs, w, label)
        print("%-10s %8.4f %8.4f %9.3f %9.3f %13.3f"
              % (r["label"], r["ns_auc"], r["fs_auc"], r["ns_top1"], r["fs_top1"], r["within_gap_mean"]))


if __name__ == "__main__":
    main()

"""Bootstrap CIs for the change-id validation over a BigQuery slice. Reports (1) the label-DISJOINT
per-axis + tx-level pre<->post results — the valid validation — and (2) the cluster findNext
circularity demonstration. Run from repo root: python3 examples/bootstrap_change_id.py (expects
slice.json in the working directory)."""
import math
import random


def pct(xs, p):
    xs = sorted(xs); k = (len(xs) - 1) * p / 100; lo = math.floor(k); hi = math.ceil(k)
    return xs[lo] if lo == hi else xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def main():
    import decluster.change_cluster as cc
    from decluster.change_slice import load_slice, build_gt_slice_mn, slice_fetchers
    from decluster.change_validate import AXES, axis_vote, output_score
    from decluster.change_cluster import build_cluster_fingerprints, cluster_rates
    from decluster.combiner import Combiner
    from decluster.extractors import x_change_index
    from decluster.graph_deanon import auc

    by_txid, spender, uf = load_slice(['slice.json'])
    gt, dropped = build_gt_slice_mn(by_txid, uf)
    get_tx, get_os = slice_fetchers(by_txid, spender)
    cmb = Combiner.from_library()
    n = len(gt)
    print(f"# change-id validation  n={n}  (dropped {dropped})")

    axes = list(AXES.items())
    votes = {name: [] for name, _ in axes}
    base, pos, neg = [], [], []
    for rec in gt:
        tx, ci = rec["tx"], rec["change_index"]
        for name, fn in axes:
            votes[name].append(axis_vote(tx, fn, get_tx, get_os))
        v = x_change_index(tx); base.append(0 if v == "first" else 1 if v == "last" else None)
        s0 = output_score(tx, 0, cmb, get_tx, get_os); s1 = output_score(tx, 1, cmb, get_tx, get_os)
        if s0 is not None and s1 is not None:
            pos.append(s0 if ci == 0 else s1); neg.append(s1 if ci == 0 else s0)
    votes["change_index"] = base
    labels = [rec["change_index"] for rec in gt]

    def rates(idx, vl):
        tp = fp = cov = 0
        for i in idx:
            vv = vl[i]
            if vv is None: continue
            cov += 1; tp += (vv == labels[i]); fp += (vv != labels[i])
        m = len(idx)
        return tp / m, fp / m, cov / m

    rng = random.Random(7); B = 2000
    names = [a for a, _ in axes] + ["change_index"]
    boot = {k: {"tpr": [], "fpr": [], "cov": []} for k in names}
    aucs, sh_aucs, npair = [], [], len(pos)
    for b in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        for k in names:
            t, f, c = rates(idx, votes[k])
            boot[k]["tpr"].append(t); boot[k]["fpr"].append(f); boot[k]["cov"].append(c)
        pidx = [rng.randrange(npair) for _ in range(npair)]
        P = [pos[i] for i in pidx]; N = [neg[i] for i in pidx]
        aucs.append(auc(P, N, seed=b))                     # seed varies per draw -> real MC variance
        flip = [rng.random() < 0.5 for _ in range(npair)]  # shuffle-null: randomize pos/neg direction
        aucs_sh = auc([P[i] if flip[i] else N[i] for i in range(npair)],
                      [N[i] if flip[i] else P[i] for i in range(npair)], seed=b)
        sh_aucs.append(aucs_sh)

    print("\n# label-DISJOINT validation (change = output whose spender agrees with T on the axis):")
    print("%-16s %-22s %6s %6s %6s" % ("axis", "TPR [2.5, 97.5]", "FPR", "cov", "prec"))
    for k in names:
        t = boot[k]["tpr"]; f = boot[k]["fpr"]; c = boot[k]["cov"]
        mt = sum(t) / B; mc = sum(c) / B
        print("%-16s %.3f [%.3f, %.3f]  %6.3f %6.3f %6.2f" % (
            k, mt, pct(t, 2.5), pct(t, 97.5), sum(f) / B, mc, mt / mc if mc else 0))
    print("combined tx-level pre<->post AUC: %.3f [%.3f, %.3f]   shuffle-null: %.3f [%.3f, %.3f]  (n_paired=%d)" % (
        sum(aucs) / B, pct(aucs, 2.5), pct(aucs, 97.5),
        sum(sh_aucs) / B, pct(sh_aucs, 2.5), pct(sh_aucs, 97.5), npair))

    # cluster findNext is CIRCULAR against the co-spend label (kept only as a demonstration).
    tfc, afc, cidx = build_cluster_fingerprints(by_txid, uf)
    real = cluster_rates(gt, uf, tfc, afc, cidx, get_tx, get_os, use_afc=False)
    cc.tx_features = lambda tx: ("CONST",)                 # null the entire construction fingerprint
    tfc0, afc0, cidx0 = build_cluster_fingerprints(by_txid, uf)
    nulled = cluster_rates(gt, uf, tfc0, afc0, cidx0, get_tx, get_os, use_afc=False)
    print("\n# cluster findNext is CIRCULAR vs the co-spend label (NOT fingerprint evidence):")
    print("  findNext TFC+changeC (real features):  TPR=%.3f FPR=%.3f cov=%.3f" % real)
    print("  findNext with fingerprint NULLED:      TPR=%.3f FPR=%.3f cov=%.3f  <- pure label structure" % nulled)


if __name__ == "__main__":
    main()

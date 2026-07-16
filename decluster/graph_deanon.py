"""Narayanan-Shmatikov probe: does graph structure predict same-owner beyond co-spend?
Ground truth = transitive common-input clusters; held-out positives = same-owner pairs
NOT directly co-spent, scored by common neighbors. `evaluate` runs the 1-hop probe;
`analyze` sweeps graph depth k (hubs excluded) to show structure is deeper under churn.
usage: python3 -m decluster.graph_deanon [--depth] <slice.json...>"""
import sys, random
from .measure import load_unique
from .unionfind import UF
from .change_gt import union_input_addrs

HUBCAP = 100      # don't expand through hubs (degree > this) — avoids small-world collapse
SIZECAP = 6000    # cap neighborhood growth


def build(sample):
    """neigh_pay excludes co-spend adjacency (which defines the ground truth) so the
    payment-only score is not circular. Returns (uf, neigh_full, neigh_pay, cospent)."""
    uf = UF()
    neigh_full, neigh_pay, cospent = {}, {}, set()
    for tx, _ in sample:
        in_addr = [v.get("prevout", {}).get("scriptpubkey_address") for v in tx.get("vin", [])]
        in_addr = [a for a in in_addr if a]
        out_addr = [o.get("scriptpubkey_address") for o in tx.get("vout", []) if o.get("scriptpubkey_address")]
        union_input_addrs(tx, uf)
        for i in range(len(in_addr)):
            for j in range(i + 1, len(in_addr)):
                cospent.add(frozenset((in_addr[i], in_addr[j])))
        parts = set(in_addr) | set(out_addr)
        for a in parts:
            neigh_full.setdefault(a, set()).update(parts - {a})
        for a in in_addr:
            neigh_pay.setdefault(a, set()).update(out_addr)
        for o in out_addr:
            neigh_pay.setdefault(o, set()).update(in_addr)
    return uf, neigh_full, neigh_pay, cospent


def structural_score(a, b, neigh):
    """common neighbors (classic link prediction)."""
    return len(neigh.get(a, set()) & neigh.get(b, set()))


def auc(pos_scores, neg_scores, seed=0):
    """AUC = P(a positive pair scores above a negative pair)."""
    rng = random.Random(seed)
    if not pos_scores or not neg_scores: return None
    trials = min(20000, len(pos_scores) * len(neg_scores))
    wins = 0.0
    for _ in range(trials):
        p, n = rng.choice(pos_scores), rng.choice(neg_scores)
        wins += 1.0 if p > n else (0.5 if p == n else 0.0)
    return wins / trials


def _pairs(clusters, neigh, cospent, rng, cap=5000):
    """positives = same cluster but not directly co-spent (held-out); negatives = cross-cluster."""
    pos, neg = [], []
    for members in clusters.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = members[i], members[j]
                if frozenset((a, b)) in cospent: continue
                pos.append(structural_score(a, b, neigh))
    roots = list(clusters)
    for _ in range(cap):
        if len(roots) < 2: break
        r1, r2 = rng.sample(roots, 2)
        neg.append(structural_score(rng.choice(clusters[r1]), rng.choice(clusters[r2]), neigh))
    return pos, neg


def _clusters(uf, neigh):
    clusters = {}
    for a in list(neigh):
        clusters.setdefault(uf.find(a), []).append(a)
    return {r: m for r, m in clusters.items() if len(m) >= 2}


def evaluate(sample, seed=0):
    uf, neigh_full, neigh_pay, cospent = build(sample)
    clusters = _clusters(uf, neigh_full)
    rng = random.Random(seed)
    pf, nf = _pairs(clusters, neigh_full, cospent, rng)
    pp, np_ = _pairs(clusters, neigh_pay, cospent, rng)
    alla = list(neigh_full)
    fake = {}
    for a in alla:
        fake.setdefault(rng.randrange(len(clusters) or 1), []).append(a)
    fake = {k: v for k, v in fake.items() if len(v) >= 2}
    ps, ns = _pairs(fake, neigh_full, set(), rng)   # shuffle control -> AUC ~0.5
    return {
        "addrs": len(alla), "clusters_ge2": len(clusters),
        "pos_pairs": len(pf), "neg_pairs": len(nf),
        "auc_full": auc(pf, nf, seed), "pos_mean_full": (sum(pf) / len(pf)) if pf else None,
        "auc_payment": auc(pp, np_, seed), "pos_mean_payment": (sum(pp) / len(pp)) if pp else None,
        "auc_shuffle": auc(ps, ns, seed),
    }


def _nk(x, pay, k, cache):
    if (x, k) in cache: return cache[(x, k)]
    seen = {x}; frontier = {x}
    for _ in range(k):
        nxt = set()
        for u in frontier:
            if u != x and len(pay.get(u, ())) > HUBCAP: continue
            nxt |= pay.get(u, set())
        frontier = nxt - seen; seen |= nxt
        if len(seen) > SIZECAP: break
    seen.discard(x); cache[(x, k)] = seen
    return seen


def analyze(sample, ks=(1, 2, 3, 4), cap=1500, seed=0):
    """Depth sweep: k-hop common neighbors (hubs excluded) vs held-out same-owner pairs."""
    uf, _full, pay, cospent = build(sample)
    clusters = _clusters(uf, pay)
    rng = random.Random(seed)
    allp = [(m[i], m[j]) for m in clusters.values()
            for i in range(len(m)) for j in range(i + 1, len(m))
            if frozenset((m[i], m[j])) not in cospent]
    if not allp:
        return {"entities": len(clusters), "pairs": 0, "share_pct": 0.0, "ks": ks, "aucs": [None] * len(ks)}
    pos = allp if len(allp) <= cap else rng.sample(allp, cap)
    roots = list(clusters)
    neg = [(rng.choice(clusters[a]), rng.choice(clusters[b]))
           for a, b in (rng.sample(roots, 2) for _ in range(cap))]
    share = 100 * sum(1 for a, b in pos if pay.get(a, set()) & pay.get(b, set())) / len(pos)
    cache, aucs = {}, []
    for k in ks:
        ps = [len(_nk(a, pay, k, cache) & _nk(b, pay, k, cache)) for a, b in pos]
        ns = [len(_nk(a, pay, k, cache) & _nk(b, pay, k, cache)) for a, b in neg]
        aucs.append(auc(ps, ns, seed))
    return {"entities": len(clusters), "pairs": len(allp), "share_pct": share, "ks": ks, "aucs": aucs}


def _load(paths):
    return load_unique(paths)


if __name__ == "__main__":
    if "--depth" in sys.argv:
        ks = (1, 2, 3, 4)
        print("%-14s %7s %8s %7s  %s" % ("slice", "entities", "pairs", "share%", "  ".join("k=%d" % k for k in ks)))
        for p in [a for a in sys.argv[1:] if a != "--depth"]:
            s = _load([p])
            heights = [int(tx.get("height", 0)) for tx, _ in s]
            r = analyze(s, ks=ks)
            print("blk %-10d %7d %8d %6.0f%%  %s" % (
                min(heights) if heights else 0, r["entities"], r["pairs"], r["share_pct"],
                "  ".join("%.2f" % a for a in r["aucs"])))
    else:
        sample = _load(sys.argv[1:])
        print(f"# {len(sample)} txs")
        r = evaluate(sample)
        print(f"addresses: {r['addrs']}  entities(>=2 addr): {r['clusters_ge2']}")
        print(f"held-out pairs (same-owner, transitive): {r['pos_pairs']}  negatives: {r['neg_pairs']}")
        print(f"AUC FULL     (co-spend+payment): {r['auc_full']:.4f}  pos_mean={r['pos_mean_full']:.2f}")
        print(f"AUC PAYMENT  (no co-spend, honest): {r['auc_payment']:.4f}  pos_mean={r['pos_mean_payment']:.2f}")
        print(f"AUC SHUFFLE  (control, ~0.5 expected): {r['auc_shuffle']:.4f}")

"""Load a contiguous BigQuery slice (bigquery/slice.sql) and build M&N same-owner change labels by
multi-input CLUSTER membership — feasible because the whole slice is in memory. The slice's vin
carries funding txid+vout (forward-spend) and prevout address (clustering), so one export gives
labeling, forward-spend, and fingerprints offline. slice_fetchers matches the injected
get_tx/get_outspends interface, so change_score/change_validate run unchanged over the slice."""
from .measure import load_unique
from .unionfind import UF
from .change_gt import is_candidate, input_addrs, out_addr, union_input_addrs

def index_slice(txs):
    """-> (by_txid, spender, uf). by_txid: txid->tx; spender: (funding_txid, vout)->spending txid;
    uf: multi-input clustering over input addresses."""
    by_txid, spender, uf = {}, {}, UF()
    for tx in txs:
        by_txid[tx["txid"]] = tx
        union_input_addrs(tx, uf)
        for v in tx["vin"]:
            ft, fv = v.get("txid"), v.get("vout")
            if ft is not None and fv is not None:
                spender[(ft, fv)] = tx["txid"]
    return by_txid, spender, uf

def load_slice(paths):
    return index_slice([tx for tx, _ in load_unique(paths)])

def slice_fetchers(by_txid, spender):
    """get_tx / get_outspends closures over the slice, matching change_score/change_validate."""
    def get_tx(txid):
        return by_txid[txid]
    def get_outspends(txid):
        tx = by_txid[txid]
        return [{"spent": (txid, i) in spender, "txid": spender.get((txid, i))}
                for i in range(len(tx["vout"]))]
    return get_tx, get_outspends

def label_by_cluster(tx, uf):
    """change = the output whose address is in T's input cluster (multi-input reveal), when exactly
    one output is; fresh filter drops a change that reuses an input address. Returns 0/1 or None.
    Label reads only addresses/co-spend (uf) — disjoint from the fingerprint the scorer uses."""
    if not is_candidate(tx): return None
    ia = input_addrs(tx)
    if not ia: return None
    root = uf.find(next(iter(ia)))
    inc = [i for i in (0, 1) if uf.find(out_addr(tx, i)) == root]
    if len(inc) != 1: return None
    ci = inc[0]
    if out_addr(tx, ci) in ia: return None
    return ci

def build_gt_slice(by_txid, uf):
    gt = []
    for tx in by_txid.values():
        ci = label_by_cluster(tx, uf)
        if ci is not None:
            gt.append({"tx": tx, "change_index": ci})
    return gt

def _output_counts(by_txid):
    from collections import Counter
    c = Counter()
    for tx in by_txid.values():
        for o in tx["vout"]:
            a = o.get("scriptpubkey_address")
            if a: c[a] += 1
    return c

def _cluster_twochange_frac(by_txid, uf):
    """per cluster root: fraction of its 2-output candidate txs whose BOTH outputs are in the
    cluster (M&N 'two change candidates')."""
    from collections import defaultdict
    tot, both = defaultdict(int), defaultdict(int)
    for tx in by_txid.values():
        if not is_candidate(tx): continue
        ia = input_addrs(tx)
        if not ia: continue
        root = uf.find(next(iter(ia)))
        tot[root] += 1
        if all(uf.find(out_addr(tx, i)) == root for i in (0, 1)):
            both[root] += 1
    return {r: both[r] / tot[r] for r in tot}

def build_gt_slice_mn(by_txid, uf, twochange_max=0.10):
    """M&N §2.2-faithful GT: cluster-membership label (build_gt_slice) plus two filters —
    (A) FRESH change: the change address is used as an output only in T (drops reused-change
    services, M&N's largest filter); (B) exclude txs from clusters where >twochange_max of their
    2-output txs have both outputs in-cluster (self-churn). Returns (gt, dropped_counts).
    NOTE: M&N's supercluster/tag-based collapse removal (Mt.Gox) needs whole-chain tags and is NOT
    applied here."""
    outc = _output_counts(by_txid)
    frac = _cluster_twochange_frac(by_txid, uf)
    gt, dropped = [], {"reused_change": 0, "twochange_cluster": 0}
    for tx in by_txid.values():
        ci = label_by_cluster(tx, uf)
        if ci is None: continue
        if outc.get(out_addr(tx, ci), 0) > 1:
            dropped["reused_change"] += 1; continue
        root = uf.find(next(iter(input_addrs(tx))))
        if frac.get(root, 0.0) > twochange_max:
            dropped["twochange_cluster"] += 1; continue
        gt.append({"tx": tx, "change_index": ci})
    return gt, dropped

if __name__ == "__main__":
    import sys
    from .change_validate import report
    by_txid, spender, uf = load_slice(sys.argv[1:])
    gt, dropped = build_gt_slice_mn(by_txid, uf)
    get_tx, get_outspends = slice_fetchers(by_txid, spender)
    print("# slice: %d txs, %d GT (M&N-filtered; dropped %r)" % (len(by_txid), len(gt), dropped))
    print(report(gt, get_tx=get_tx, get_outspends=get_outspends))

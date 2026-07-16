"""Kappos cluster-level change identification (findNext): change = the output at the input cluster's
change-index (changeC) whose address type is in the cluster's set (AFC) and whose onward-spend's
construction features are in the cluster's set (TFC), when exactly one output qualifies. Leave-one-out
removes the candidate tx T from its own cluster's sets before predicting T. AFC is skipped when the
cluster carries no address-type info (the lean slice export drops scriptpubkey_type; here it is
approximated from address prefixes, _addr_type).

CIRCULARITY WARNING: against an M&N co-spend label this scorer is circular — the change's onward-
spender IS the co-spend reveal tx (a cluster member by construction), so "features in TFC" reduces to
cluster membership = the label (empirically: nulling the fingerprint still scores ~0.66). findNext is
kept for the method, but its accuracy is a label-consistency upper bound, not fingerprint evidence;
the label-disjoint validation lives in change_validate (per-axis) and change_score (tx-level).
See results/RESULTS-change-id.md."""
from collections import Counter
from .extractors import x_nsequence, x_version
from .change_gt import input_addrs, out_addr

def _locktime_policy(tx): return "zero" if tx.get("locktime", 0) == 0 else "height"

def _addr_type(addr):
    """derive the script type from a mainnet address prefix/length (so AFC works even when the slice
    export drops scriptpubkey_type)."""
    if not addr: return None
    if addr.startswith("bc1p"): return "v1_p2tr"
    if addr.startswith("bc1q"): return "v0_p2wpkh" if len(addr) <= 42 else "v0_p2wsh"
    if addr.startswith("bc1"): return "v0_unknown"
    if addr.startswith("1"): return "p2pkh"
    if addr.startswith("3"): return "p2sh"
    return "nonstandard"

def _o_type(o):
    """explicit scriptpubkey_type if present, else derived from the address."""
    return o.get("scriptpubkey_type") or _addr_type(o.get("scriptpubkey_address"))

def tx_features(tx):
    """Kappos TFC element: a construction feature tuple (nsequence, locktime, version)."""
    return (x_nsequence(tx), _locktime_policy(tx), x_version(tx))

def _out_types(tx):
    return Counter(t for o in tx["vout"] if (t := _o_type(o)))

def change_strategy(indices):
    """Kappos changeC from observed change indices (0=first, -1=last): 0 (always first), -1 (always
    last), 1 (always first-or-last), None otherwise. Empty -> None."""
    s = set(indices)
    if not s: return None
    if s == {0}: return 0
    if s == {-1}: return -1
    if s <= {0, -1}: return 1
    return None

def _cluster_change_idx(tx, root, uf):
    """the single output index whose address is in T's cluster and is fresh (not an input), as
    0 (first) / -1 (last) / the raw index; None if not exactly one such output."""
    ia = input_addrs(tx)
    n = len(tx["vout"])
    incl = [i for i in range(n)
            if out_addr(tx, i) is not None and out_addr(tx, i) not in ia
            and uf.find(out_addr(tx, i)) == root]
    if len(incl) != 1: return None
    i = incl[0]
    return 0 if i == 0 else (-1 if i == n - 1 else i)

def build_cluster_fingerprints(by_txid, uf):
    """root -> aggregated fingerprints. Returns (tfc, afc, cidx):
    tfc[root]: Counter of tx-feature tuples; afc[root]: Counter of output address types;
    cidx[root]: list of (txid, change_index) for changeC. Counters allow leave-one-out."""
    tfc, afc, cidx = {}, {}, {}
    for tx in by_txid.values():
        ia = input_addrs(tx)
        if not ia: continue
        root = uf.find(next(iter(ia)))
        tfc.setdefault(root, Counter())[tx_features(tx)] += 1
        afc.setdefault(root, Counter()).update(_out_types(tx))
        ci = _cluster_change_idx(tx, root, uf)
        if ci is not None:
            cidx.setdefault(root, []).append((tx["txid"], ci))
    return tfc, afc, cidx

def _candidate_indices(n, changeC):
    if changeC in (0, -1): return [changeC % n]
    if changeC == 1: return [0, n - 1]
    return list(range(n))            # None -> all outputs

def find_change(tx, uf, tfc, afc, cidx, get_tx, get_outspends, use_afc=True):
    """Kappos findNext with leave-one-out: predict T's change index or None (abstain). use_afc=False
    drops the address-type (AFC/baddr) check — on modern data type homogeneity makes AFC add noise,
    a degradation Kappos anticipated (change-type matching the counterparty)."""
    ia = input_addrs(tx)
    if not ia: return None
    root = uf.find(next(iter(ia)))
    tf = tx_features(tx)
    ot = _out_types(tx)
    # leave-one-out cluster sets (exclude T's own contribution)
    eff_tfc = {t for t, c in tfc.get(root, {}).items() if c - (t == tf) > 0}
    eff_afc = {t for t, c in afc.get(root, {}).items() if c - ot.get(t, 0) > 0}
    eff_idx = change_strategy([i for (tid, i) in cidx.get(root, []) if tid != tx["txid"]])
    n = len(tx["vout"])
    spends = get_outspends(tx["txid"])
    passed = []
    for i in _candidate_indices(n, eff_idx):
        if i >= n: continue
        s = spends[i]
        if not s.get("spent"): continue                          # bnext
        if use_afc and eff_afc and (ot_i := _o_type(tx["vout"][i])):
            if ot_i not in eff_afc: continue                     # baddr (skip if no type info)
        if tx_features(get_tx(s["txid"])) not in eff_tfc: continue  # btx
        passed.append(i)
    return passed[0] if len(passed) == 1 else None

def cluster_rates(gt, uf, tfc, afc, cidx, get_tx, get_outspends, use_afc=True):
    """(tpr, fpr, coverage) of cluster-level findNext over GT. TP: predict == change label;
    FP: predict == spend. Denominator = len(gt)."""
    n = len(gt) or 1
    tp = fp = cov = 0
    for rec in gt:
        v = find_change(rec["tx"], uf, tfc, afc, cidx, get_tx, get_outspends, use_afc)
        if v is None: continue
        cov += 1
        if v == rec["change_index"]: tp += 1
        else: fp += 1
    return (tp / n, fp / n, cov / n)

if __name__ == "__main__":
    import sys
    from .change_slice import load_slice, build_gt_slice_mn, slice_fetchers
    by_txid, spender, uf = load_slice(sys.argv[1:])
    gt, _dropped = build_gt_slice_mn(by_txid, uf)
    get_tx, get_outspends = slice_fetchers(by_txid, spender)
    tfc, afc, cidx = build_cluster_fingerprints(by_txid, uf)
    print("# cluster-level findNext (Kappos) — CIRCULAR vs a co-spend label; not a fingerprint result")
    print("%-26s %6s %6s %8s" % ("scorer", "TPR", "FPR", "coverage"))
    for lbl, use in (("findNext (TFC+changeC)", False), ("findNext +AFC (prefix-approx)", True)):
        tpr, fpr, cov = cluster_rates(gt, uf, tfc, afc, cidx, get_tx, get_outspends, use)
        print("%-26s %6.3f %6.3f %8.3f" % (lbl, tpr, fpr, cov))

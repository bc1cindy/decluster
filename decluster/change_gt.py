"""M&N change-identification primitives shared by the slice pipeline: which 2-output transactions
are candidates, and their input/output addresses. The change label — co-spend cluster membership —
is built in change_slice; it is an address-graph signal, disjoint from the T-vs-spender construction
fingerprints the per-axis (change_validate) and tx-level (change_score) scorers use, so those tests
are not circular. (The cluster findNext in change_cluster instead tests cluster membership and IS
circular against this label — see its docstring.)"""

def input_addrs(tx):
    return {a for v in tx["vin"] if (a := (v.get("prevout") or {}).get("scriptpubkey_address"))}

def union_input_addrs(tx, uf):
    """Union a transaction's input addresses into uf (multi-input co-spend clustering)."""
    ins = list(input_addrs(tx))
    for a in ins[1:]:
        uf.union(ins[0], a)

def out_addr(tx, i):
    return tx["vout"][i].get("scriptpubkey_address")

def is_candidate(tx):
    """M&N core: exactly two spendable outputs (both carry an address)."""
    outs = tx.get("vout", [])
    return len(outs) == 2 and all(o.get("scriptpubkey_address") for o in outs)

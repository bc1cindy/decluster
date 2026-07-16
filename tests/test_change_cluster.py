"""Kappos cluster-level findNext: change decided by the input cluster's TFC/AFC/changeC vs each
output's onward-spend, with leave-one-out so T's own features/index don't leak the label."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.change_cluster import (
    tx_features, change_strategy, build_cluster_fingerprints, find_change, cluster_rates)
from decluster.change_slice import index_slice, slice_fetchers

def _tx(txid, ins, outs, seq=0xFFFFFFFD, lt=0, ver=2, otypes=None):
    """ins: [(funding_txid, vout, addr)]; outs: [addr]; otypes: per-output scriptpubkey_type."""
    otypes = otypes or ["v0_p2wpkh"] * len(outs)
    return {"txid": txid, "locktime": lt, "version": ver,
            "vin": [{"txid": ft, "vout": fv, "sequence": seq,
                     "prevout": {"scriptpubkey_address": a}} for (ft, fv, a) in ins],
            "vout": [{"value": 50000 + i, "scriptpubkey_address": a, "scriptpubkey_type": t}
                     for i, (a, t) in enumerate(zip(outs, otypes))]}

def test_addr_type_from_prefix():
    from decluster.change_cluster import _addr_type
    assert _addr_type("bc1phu40z82qfvk7dgvmhcwz40caqluk4ad6aezupxeteeqwcz2fmjgsk5e8z7") == "v1_p2tr"
    assert _addr_type("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq") == "v0_p2wpkh"
    assert _addr_type("bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3") == "v0_p2wsh"
    assert _addr_type("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2") == "p2pkh"
    assert _addr_type("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") == "p2sh"
    assert _addr_type("nonstandard6ddf9ca57d83c310859f41cc33abbcb7fb5c5fbf") == "nonstandard"
    assert _addr_type(None) is None

def test_tx_features_tuple():
    assert tx_features(_tx("T", [("f", 0, "a")], ["b"], seq=0xFFFFFFFD, lt=0, ver=2)) == \
        ("rbf_fffffffd", "zero", "v2")

def test_change_strategy():
    assert change_strategy([0, 0, 0]) == 0
    assert change_strategy([-1, -1]) == -1
    assert change_strategy([0, -1, 0]) == 1
    assert change_strategy([0, 1]) is None
    assert change_strategy([]) is None

def test_build_and_findNext_picks_cluster_consistent_output():
    # cluster of I1: two txs (T, U) that both put change at index 0, spent by txs with the cluster's
    # tx-features; a decoy tx D at index 1 spent by a tx with a DIFFERENT feature tuple.
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    U = _tx("U", [("PU", 0, "I1")], ["C2", "PU2"])
    # reveals: C and C2 co-spent with I1 -> cluster; their spenders carry the cluster tx-features
    RC = _tx("RC", [("T", 0, "C"), ("W", 9, "I1")], ["x"])
    RC2 = _tx("RC2", [("U", 0, "C2"), ("W", 8, "I1")], ["y"])
    # T's payment output P spent by a tx with a DIFFERENT feature tuple (locktime set)
    RP = _tx("RP", [("T", 1, "P")], ["z"], lt=800000)
    U_RP = _tx("URP", [("U", 1, "PU2")], ["w"], lt=800000)
    by, sp, uf = index_slice([T, U, RC, RC2, RP, U_RP])
    get_tx, get_os = slice_fetchers(by, sp)
    tfc, afc, cidx = build_cluster_fingerprints(by, uf)
    # predicting T: leave-one-out uses U's change@0 (changeC=0) + U's spender features in TFC
    assert find_change(T, uf, tfc, afc, cidx, get_tx, get_os) == 0

def test_findNext_abstains_singleton_cluster_leave_one_out():
    # cluster is just T -> after leave-one-out, changeC/TFC are empty -> cannot decide -> abstain
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    RC = _tx("RC", [("T", 0, "C"), ("W", 9, "I1")], ["x"])
    RP = _tx("RP", [("T", 1, "P")], ["z"])
    by, sp, uf = index_slice([T, RC, RP])
    get_tx, get_os = slice_fetchers(by, sp)
    tfc, afc, cidx = build_cluster_fingerprints(by, uf)
    # T is the only tx in its cluster -> eff_tfc empty -> btx fails for all -> abstain
    assert find_change(T, uf, tfc, afc, cidx, get_tx, get_os) is None

def test_afc_filters_by_address_type():
    # two cluster txs establish AFC={v0_p2wpkh}; a candidate whose spent output is p2pkh is rejected
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"], otypes=["p2pkh", "v0_p2wpkh"])
    U = _tx("U", [("PU", 0, "I1")], ["C2", "PU2"], otypes=["v0_p2wpkh", "v0_p2wpkh"])
    RC = _tx("RC", [("T", 0, "C"), ("W", 9, "I1")], ["x"])
    RC2 = _tx("RC2", [("U", 0, "C2"), ("W", 8, "I1")], ["y"])
    RP = _tx("RP", [("T", 1, "P")], ["z"])
    U_RP = _tx("URP", [("U", 1, "PU2")], ["w"])
    by, sp, uf = index_slice([T, U, RC, RC2, RP, U_RP])
    get_tx, get_os = slice_fetchers(by, sp)
    tfc, afc, cidx = build_cluster_fingerprints(by, uf)
    # T's change output (idx0) is p2pkh; leave-one-out AFC (from U) = {v0_p2wpkh} -> baddr rejects
    # idx0, so no candidate passes -> abstain (not a wrong pick)
    assert find_change(T, uf, tfc, afc, cidx, get_tx, get_os) is None

def test_cluster_rates_concrete():
    # both GT txs put change at idx0; each is predicted correctly from its sibling -> (1, 0, 1)
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    U = _tx("U", [("PU", 0, "I1")], ["C2", "PU2"])
    RC = _tx("RC", [("T", 0, "C"), ("W", 9, "I1")], ["x"])
    RC2 = _tx("RC2", [("U", 0, "C2"), ("W", 8, "I1")], ["y"])
    RP = _tx("RP", [("T", 1, "P")], ["z"]); U_RP = _tx("URP", [("U", 1, "PU2")], ["w"])
    by, sp, uf = index_slice([T, U, RC, RC2, RP, U_RP])
    get_tx, get_os = slice_fetchers(by, sp)
    tfc, afc, cidx = build_cluster_fingerprints(by, uf)
    gt = [{"tx": T, "change_index": 0}, {"tx": U, "change_index": 0}]
    assert cluster_rates(gt, uf, tfc, afc, cidx, get_tx, get_os) == (1.0, 0.0, 1.0)

def test_use_afc_false_recovers_what_afc_rejects():
    # same fixture as test_afc_filters_by_address_type: AFC (True) rejects the p2pkh change and
    # abstains; use_afc=False drops the address-type check and picks the correct index (0).
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"], otypes=["p2pkh", "v0_p2wpkh"])
    U = _tx("U", [("PU", 0, "I1")], ["C2", "PU2"], otypes=["v0_p2wpkh", "v0_p2wpkh"])
    RC = _tx("RC", [("T", 0, "C"), ("W", 9, "I1")], ["x"])
    RC2 = _tx("RC2", [("U", 0, "C2"), ("W", 8, "I1")], ["y"])
    RP = _tx("RP", [("T", 1, "P")], ["z"]); U_RP = _tx("URP", [("U", 1, "PU2")], ["w"])
    by, sp, uf = index_slice([T, U, RC, RC2, RP, U_RP])
    get_tx, get_os = slice_fetchers(by, sp)
    tfc, afc, cidx = build_cluster_fingerprints(by, uf)
    assert find_change(T, uf, tfc, afc, cidx, get_tx, get_os, use_afc=True) is None
    assert find_change(T, uf, tfc, afc, cidx, get_tx, get_os, use_afc=False) == 0

def test_changeC_alone_picks_change_documents_circularity():
    # Honesty check: even with the construction fingerprint NULLED, changeC (the cluster's
    # change-index habit — itself derived from co-spend membership = the label) alone still picks the
    # change. This documents why findNext is circular against a co-spend label.
    import decluster.change_cluster as cc
    T = _tx("T", [("PF", 0, "I1")], ["C", "P"])
    U = _tx("U", [("PU", 0, "I1")], ["C2", "PU2"])          # sibling: change at idx0
    RC = _tx("RC", [("T", 0, "C"), ("W", 9, "I1")], ["x"])
    RC2 = _tx("RC2", [("U", 0, "C2"), ("W", 8, "I1")], ["y"])
    RP = _tx("RP", [("T", 1, "P")], ["z"]); U_RP = _tx("URP", [("U", 1, "PU2")], ["w"])
    by, sp, uf = index_slice([T, U, RC, RC2, RP, U_RP])
    get_tx, get_os = slice_fetchers(by, sp)
    orig = cc.tx_features
    try:
        cc.tx_features = lambda tx: ("CONST",)              # zero fingerprint content
        tfc, afc, cidx = build_cluster_fingerprints(by, uf)
        assert find_change(T, uf, tfc, afc, cidx, get_tx, get_os, use_afc=False) == 0
    finally:
        cc.tx_features = orig

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")

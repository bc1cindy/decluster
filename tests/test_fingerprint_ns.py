import math
from decluster import fingerprint_ns as fns

def test_signature_includes_only_weighted_features():
    axis_fns = [("version", lambda tx: tx["v"]), ("op_return", lambda tx: tx["o"])]
    weights = {("version", "v2"): 1.4, ("op_return", "none"): 0.1}
    sig = fns.fingerprint_signature({"v": "v2", "o": "none"}, axis_fns, weights)
    assert sig == {("version", "v2"): 1.4, ("op_return", "none"): 0.1}
    # an unweighted value is dropped, not crediting rarity we never measured
    sig2 = fns.fingerprint_signature({"v": "v99", "o": "none"}, axis_fns, weights)
    assert sig2 == {("op_return", "none"): 0.1}

def test_link_is_symmetric_agreement_overlap():
    a = {("version", "v2"): 1.4, ("op_return", "none"): 0.1, ("low_r", "low_r"): 2.3}
    b = {("version", "v2"): 1.4, ("op_return", "has_op_return"): 4.0, ("low_r", "low_r"): 2.3}
    assert fns.fingerprint_link(a, b) == 1.4 + 2.3        # version + low_r agree; op_return differs
    assert fns.fingerprint_link(a, b) == fns.fingerprint_link(b, a)
    assert fns.fingerprint_link(a, {}) == 0.0

def test_measured_weights_are_neg_log2_share():
    axis_fns = [("op_return", lambda tx: tx["o"])]
    txs = [{"o": "none"}, {"o": "none"}, {"o": "none"}, {"o": "has_op_return"}]  # 3/4, 1/4
    w = fns.measured_weights(txs, axis_fns)
    assert abs(w[("op_return", "none")] - -math.log2(0.75)) < 1e-9
    assert abs(w[("op_return", "has_op_return")] - -math.log2(0.25)) < 1e-9

def test_lumen_weights_fall_back_when_absent(tmp_path):
    p = tmp_path / "prior.json"
    p.write_text('{"op_return": {"none": 1.28, "has_op_return": 0.77}}')
    fallback = {("op_return", "none"): 0.09, ("version", "v2"): 1.42}
    w = fns.lumen_weights(str(p), fallback)
    assert w[("op_return", "none")] == 1.28            # from lumen
    assert w[("version", "v2")] == 1.42                # fell back to library

def test_library_weights_cover_known_axis():
    w = fns.library_weights()
    assert ("op_return", "none") in w and w[("op_return", "none")] > 0

def test_pairwise_auc_perfect_on_separable_toy():
    axis_fns = [("a", lambda tx: tx["a"])]
    weights = {("a", "x"): 3.0, ("a", "y"): 3.0}
    # positives agree (overlap 3.0); negatives disagree (overlap 0.0) -> AUC 1.0
    pos = [({"a": "x"}, {"a": "x"}), ({"a": "y"}, {"a": "y"})]
    neg = [({"a": "x"}, {"a": "y"}), ({"a": "y"}, {"a": "x"})]
    assert fns.pairwise_auc(pos, neg, axis_fns, weights) == 1.0

def test_reid_gap_collapses_within_one_equivalence_class():
    # all candidates share the query's fingerprint -> equal scores -> gap 0 (conditioner prediction)
    axis_fns = [("a", lambda tx: tx["a"])]
    weights = {("a", "x"): 3.0}
    q = {"a": "x"}
    cands = [{"a": "x"}, {"a": "x"}, {"a": "x"}]
    r = fns.reid_gap(q, cands, axis_fns, weights)
    assert r["gap"] == 0.0

def test_reid_gap_is_high_with_one_dominant_match():
    axis_fns = [("a", lambda tx: tx["a"]), ("b", lambda tx: tx["b"])]
    weights = {("a", "x"): 3.0, ("b", "y"): 3.0, ("b", "z"): 3.0}
    q = {"a": "x", "b": "y"}
    cands = [{"a": "x", "b": "y"}, {"a": "q", "b": "z"}, {"a": "q", "b": "z"}]  # cand0 dominant
    r = fns.reid_gap(q, cands, axis_fns, weights)
    assert r["best"] == 0 and r["gap"] > 0.0

def test_equivalence_key_groups_matching_conditioners():
    axis_fns = [("version", lambda tx: tx["v"]), ("nsequence", lambda tx: tx["s"])]
    k1 = fns.equivalence_key({"v": "v2", "s": "rbf"}, axis_fns, cond_axes=("version", "nsequence"))
    k2 = fns.equivalence_key({"v": "v2", "s": "rbf"}, axis_fns, cond_axes=("version", "nsequence"))
    k3 = fns.equivalence_key({"v": "v1", "s": "rbf"}, axis_fns, cond_axes=("version", "nsequence"))
    assert k1 == k2 and k1 != k3

def test_build_labeled_nodes_assigns_one_owner_per_reuse_group():
    import examples.fingerprint_ns as ex
    txs = [
        {"txid": "t1", "vin": [{"prevout": {"scriptpubkey_address": "A"}}]},
        {"txid": "t2", "vin": [{"prevout": {"scriptpubkey_address": "A"}}]},
        {"txid": "t3", "vin": [{"prevout": {"scriptpubkey_address": "B"}}]},
        {"txid": "t4", "vin": [{"prevout": {"scriptpubkey_address": "B"}}]},
    ]
    nodes = ex.build_labeled_nodes(txs, cap=10)
    owners = {tx["txid"]: owner for tx, owner in nodes}
    assert owners["t1"] == owners["t2"] and owners["t3"] == owners["t4"]
    assert owners["t1"] != owners["t3"]

def test_build_labeled_nodes_dedups_tx_that_reuses_two_addresses():
    import examples.fingerprint_ns as ex
    txs = [
        # t1 reuses both address A (with t2) and address C (with t3) -> must land in one owner only
        {"txid": "t1", "vin": [{"prevout": {"scriptpubkey_address": "A"}},
                                {"prevout": {"scriptpubkey_address": "C"}}]},
        {"txid": "t2", "vin": [{"prevout": {"scriptpubkey_address": "A"}}]},
        {"txid": "t3", "vin": [{"prevout": {"scriptpubkey_address": "C"}}]},
        {"txid": "t4", "vin": [{"prevout": {"scriptpubkey_address": "B"}}]},
        {"txid": "t5", "vin": [{"prevout": {"scriptpubkey_address": "B"}}]},
    ]
    nodes = ex.build_labeled_nodes(txs, cap=10)
    txids = [tx["txid"] for tx, _ in nodes]
    assert len(txids) == len(set(txids))  # no txid appears twice, under any owner
    owners = {tx["txid"]: owner for tx, owner in nodes}
    assert "t1" in owners
    # t1 lands in exactly one owner - group A sorts before group C, so it wins the tie
    assert owners["t1"] == owners["t2"]

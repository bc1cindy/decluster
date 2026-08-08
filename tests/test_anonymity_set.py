import math
from decluster.anonymity_set import anonymity_bits, reweight


def test_anonymity_bits_uniform_is_max_entropy():
    n = 8
    d = {i: 1.0 / n for i in range(n)}
    b = anonymity_bits(d)
    assert abs(b["min_entropy"] - math.log2(n)) < 1e-9
    assert abs(b["shannon"] - math.log2(n)) < 1e-9


def test_reweight_uniform_factors_is_noop():
    d = {0: 0.5, 1: 0.3, 2: 0.2}
    out = reweight(d, {0: 1.0, 1: 1.0, 2: 1.0})
    for k in d:
        assert abs(out[k] - d[k]) < 1e-12


def test_reweight_narrowing_decreases_entropy():
    d = {i: 0.25 for i in range(4)}          # uniform, 2 bits
    # evidence rules origins toward {0,1}: boost them, suppress {2,3}
    out = reweight(d, {0: 1.0, 1: 1.0, 2: 0.1, 3: 0.1})
    assert anonymity_bits(out)["shannon"] < anonymity_bits(d)["shannon"]


def test_reweight_indicator_collapses_to_point_mass():
    d = {i: 0.25 for i in range(4)}
    out = reweight(d, {0: 1.0, 1: 0.0, 2: 0.0, 3: 0.0})   # confidence-1: origin is 0
    assert abs(out[0] - 1.0) < 1e-9
    assert abs(anonymity_bits(out)["min_entropy"]) < 1e-9


from decluster.anonymity_set import provenance_anonymity, decay, provenance_overlap_hypothesis


def test_provenance_anonymity_reweights_a_given_base():
    base = {"o0": 0.25, "o1": 0.25, "o2": 0.25, "o3": 0.25}
    h = ("narrow", {"o0": 1.0, "o1": 1.0, "o2": 0.01, "o3": 0.01})
    out = provenance_anonymity("t", [h], base_dist=base)
    assert out["o0"] > out["o2"]
    assert abs(sum(out.values()) - 1.0) < 1e-9


def test_decay_monotone_non_increasing_for_narrowing():
    base = {i: 0.2 for i in range(5)}        # uniform, log2(5) bits
    h1 = ("h1", {0: 1.0, 1: 1.0, 2: 1.0, 3: 0.1, 4: 0.1})
    h2 = ("h2", {0: 1.0, 1: 1.0, 2: 0.1, 3: 0.1, 4: 0.1})
    trace = decay(base, [h1, h2])
    assert trace[0][0] == "graph"
    ents = [e for _, e in trace]
    assert abs(ents[0] - math.log2(5)) < 1e-9
    for a, b in zip(ents, ents[1:]):
        assert b <= a + 1e-9


def test_provenance_overlap_hypothesis_suppresses_non_overlapping():
    origins = ["o0", "o1", "o2"]
    sigs = {"o0": {"anc": 1.0}, "o1": {"anc": 1.0}, "o2": {"other": 1.0}}
    ref = {"anc": 1.0}
    name, factors = provenance_overlap_hypothesis(ref, origins, sig_of=sigs)
    assert factors["o0"] > factors["o2"]
    assert factors["o1"] > factors["o2"]


from decluster.anonymity_set import provenance_anonymity_fused, sameowner_link_oracle, anonymity_bits


def _branching_fetch():
    # target t1 output 0 has two inputs each from a tx with two grandparents -> branching origins
    txs = {
        "t1": {"vin": [{"txid": "a", "vout": 0, "prevout": {"value": 500}},
                       {"txid": "b", "vout": 0, "prevout": {"value": 500}}],
               "vout": [{"value": 1000}]},
        "a": {"vin": [{"txid": "a0", "vout": 0, "prevout": {"value": 250}},
                      {"txid": "a1", "vout": 0, "prevout": {"value": 250}}],
              "vout": [{"value": 500}]},
        "b": {"vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
        "a0": {"vin": [{"is_coinbase": True}], "vout": [{"value": 250}]},
        "a1": {"vin": [{"is_coinbase": True}], "vout": [{"value": 250}]},
    }
    return lambda txid: txs[txid]


def test_fused_sharpens_provenance_vs_graph_only():
    fetch = _branching_fetch()
    oracle = lambda ins, outs: [[1.0] for _ in ins]         # uniform links -> branching, high entropy
    graph_only = provenance_anonymity_fused(("t1", 0), None, depth=4, fetch=fetch, link_oracle=oracle)
    # subjective: at t1, output 0 came from input 0 (the 'a' side) same-owner; at 'a', from input 0
    def same_owner(tx):
        outs = tx.get("vout", [])
        ins = tx.get("vin", [])
        if len(ins) >= 1 and len(outs) >= 1:
            return {(0, 0)}                                  # pin input 0 -> output 0
        return set()
    fused = provenance_anonymity_fused(("t1", 0), sameowner_link_oracle(same_owner),
                                       depth=4, fetch=fetch, link_oracle=oracle)
    assert anonymity_bits(fused)["min_entropy"] <= anonymity_bits(graph_only)["min_entropy"] + 1e-9
    # and strictly sharper here (mass routed toward the pinned branch)
    assert anonymity_bits(fused)["shannon"] < anonymity_bits(graph_only)["shannon"]


def test_sameowner_link_oracle_boosts_named_pairs_else_abstains():
    orc = sameowner_link_oracle(lambda tx: {(0, 1)}, boost=5.0)
    m = orc({"vin": [1, 2], "vout": [1, 2, 3]}, [10, 20], [5, 10, 15])
    assert m[0][1] == 5.0 and m[0][0] == 1.0 and m[1][1] == 1.0   # only (0,1) boosted
    empty = sameowner_link_oracle(lambda tx: set())
    assert empty({"vin": [1], "vout": [1]}, [1], [1]) is None      # abstain


from decluster.anonymity_set import (change_id_pairs, address_reuse_pairs,
                                      subjective_same_owner_pairs)


def test_change_id_pairs_links_inputs_to_change():
    # 2-out: change = less-round output. 100000 (round) is payment, 90007 (less round) is change=idx1
    tx = {"vin": [{"prevout": {"value": 200000}}, {"prevout": {"value": 100}}],
          "vout": [{"value": 100000}, {"value": 90007}]}
    pairs = change_id_pairs(tx)
    assert pairs == {(0, 1), (1, 1)}          # both inputs same-owner as change output 1


def test_change_id_pairs_empty_when_no_identifiable_change():
    tx = {"vin": [{"prevout": {"value": 100}}], "vout": [{"value": 50}, {"value": 50}]}  # equal-round
    assert change_id_pairs(tx) == set()


def test_address_reuse_pairs_links_reused_address():
    tx = {"vin": [{"prevout": {"scriptpubkey_address": "a"}},
                  {"prevout": {"scriptpubkey_address": "b"}}],
          "vout": [{"scriptpubkey_address": "a"}, {"scriptpubkey_address": "x"}]}
    assert address_reuse_pairs(tx) == {(0, 0)}


def test_subjective_pairs_default_is_address_reuse_only():
    tx = {"vin": [{"prevout": {"value": 200000, "scriptpubkey_address": "a"}},
                  {"prevout": {"value": 100, "scriptpubkey_address": "b"}}],
          "vout": [{"value": 100000, "scriptpubkey_address": "a"}, {"value": 90007}]}
    # change-ID (inert, cluster-level) is no longer a default source; only address-reuse -> {(0,0)}
    assert subjective_same_owner_pairs(tx) == {(0, 0)}


def test_subjective_pairs_unions_sources_when_explicitly_passed():
    tx = {"vin": [{"prevout": {"value": 200000, "scriptpubkey_address": "a"}},
                  {"prevout": {"value": 100, "scriptpubkey_address": "b"}}],
          "vout": [{"value": 100000, "scriptpubkey_address": "a"}, {"value": 90007}]}
    # change-ID -> {(0,1),(1,1)} ; address-reuse -> {(0,0)}
    pairs = subjective_same_owner_pairs(tx, sources=(change_id_pairs, address_reuse_pairs))
    assert pairs == {(0, 1), (1, 1), (0, 0)}


def test_subjective_pairs_empty_on_ordinary_payment():
    tx = {"vin": [{"prevout": {"value": 100, "scriptpubkey_address": "a"}}],
          "vout": [{"value": 40, "scriptpubkey_address": "x"}, {"value": 40, "scriptpubkey_address": "y"}]}
    assert subjective_same_owner_pairs(tx) == set()   # equal-round change ambiguous, no reuse


from decluster.anonymity_set import (cluster_of_from_groups, cluster_of_from_tx_groups,
                                      cluster_pairs)


def test_cluster_of_from_groups_flattens():
    assert cluster_of_from_groups([["a", "b"], ["c"]]) == {"a": 0, "b": 0, "c": 1}


def test_cluster_of_from_tx_groups_maps_input_addresses_to_owner():
    # cluster_refined groups TXIDS; the bridge must expand each group into its input prevout
    # addresses (co-spend = common input ownership), NOT treat the txids themselves as addresses.
    txs = {"t1": {"vin": [{"prevout": {"scriptpubkey_address": "a"}},
                          {"prevout": {"scriptpubkey_address": "b"}}],
                  "vout": [{"scriptpubkey_address": "z"}]},
           "t2": {"vin": [{"prevout": {"scriptpubkey_address": "c"}}],
                  "vout": [{"scriptpubkey_address": "d"}]}}
    # t1,t2 same owner (one group); t2's input "c" alone in group 1 would be another owner.
    cof = cluster_of_from_tx_groups([["t1", "t2"], []], lambda t: txs[t])
    assert cof == {"a": 0, "b": 0, "c": 0}   # input addresses -> owner 0; output "z"/"d" NOT assigned


def test_cluster_pairs_links_same_cluster_input_output():
    tx = {"vin": [{"prevout": {"scriptpubkey_address": "a"}},
                  {"prevout": {"scriptpubkey_address": "z"}}],
          "vout": [{"scriptpubkey_address": "b"}, {"scriptpubkey_address": "q"}]}
    cluster_of = {"a": 0, "b": 0, "z": 1, "q": 2}   # a,b same owner; z,q separate
    assert cluster_pairs(tx, cluster_of) == {(0, 0)}   # input0(a) <-> output0(b), same cluster 0


def test_cluster_pairs_empty_when_no_shared_cluster():
    tx = {"vin": [{"prevout": {"scriptpubkey_address": "a"}}],
          "vout": [{"scriptpubkey_address": "b"}]}
    assert cluster_pairs(tx, {"a": 0, "b": 1}) == set()

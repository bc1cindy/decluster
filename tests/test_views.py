import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from decluster.views import (AXES, PseudonymGraph, cluster_addresses, contract,
                             partition_coins)


def tx(ins, outs, height=100, version=2, locktime=0, seq=0xFFFFFFFF):
    return {"txid": f"t{height}-{ins}-{outs}", "height": height, "version": version,
            "locktime": locktime, "fee": 100, "weight": 400,
            "vin": [{"txid": f"p{a}", "vout": 0, "sequence": seq,
                     "prevout": {"value": 10_000, "scriptpubkey_type": "v0_p2wpkh",
                                 "scriptpubkey_address": a}} for a in ins],
            "vout": [{"value": v, "scriptpubkey_type": "v0_p2wpkh",
                      "scriptpubkey_address": a} for a, v in outs]}


def S(*txs):
    return [(t, None) for t in txs]


# --- clustering -------------------------------------------------------------

def test_clustering_is_global_and_transitive():
    s = S(tx(["a", "b"], [("x", 500)]), tx(["b", "c"], [("y", 500)]))
    lk = cluster_addresses(s)
    assert lk["a"] == lk["b"] == lk["c"]


# --- partition --------------------------------------------------------------

def test_epoch_partition_splits_by_height():
    s = S(tx(["a"], [("x", 1)], height=10), tx(["b"], [("y", 1)], height=20))
    parts = partition_coins(s, "epoch")
    assert parts == [[0], [1]]


def test_epoch_partition_honours_explicit_bounds():
    s = S(tx(["a"], [("x", 1)], height=10), tx(["b"], [("y", 1)], height=50),
          tx(["c"], [("z", 1)], height=90))
    assert partition_coins(s, "epoch", bounds=[(0, 20), (80, 100)]) == [[0], [2]]


def test_a_cut_removes_the_boundary_and_keeps_the_rest():
    """A cut removes edges, it does not discard the vertices incident to it: the coinjoin
    itself leaves the views, every other transaction stays in one of them."""
    cj = tx(["p", "q", "r"], [("s", 1), ("t", 1), ("u", 1)], height=50)
    s = S(tx(["a"], [("x", 1)], height=10), cj, tx(["b"], [("y", 1)], height=90))
    parts = partition_coins(s, "coinjoin_boundary")
    assert 1 not in parts[0] and 1 not in parts[1]
    assert sorted(parts[0] + parts[1]) == [0, 2]


def test_ambiguity_cut_excludes_low_evidence_and_needs_a_callable():
    s = S(tx(["a"], [("x", 1)]), tx(["b"], [("y", 1)]), tx(["c"], [("z", 1)]),
          tx(["d"], [("w", 1)]))
    amb = lambda t: 0.0 if t["vin"][0]["prevout"]["scriptpubkey_address"] == "b" else 5.0
    parts = partition_coins(s, "ambiguity_cut", ambiguity=amb, theta=1.0)
    assert sorted(sum(parts, [])) == [0, 2, 3]
    with pytest.raises(ValueError):
        partition_coins(s, "ambiguity_cut")


def test_unknown_scheme_is_rejected():
    with pytest.raises(ValueError):
        partition_coins(S(tx(["a"], [("x", 1)])), "by_vibes")


# --- contraction ------------------------------------------------------------

def test_cluster_members_fuse_into_one_vertex():
    s = S(tx(["a", "b"], [("x", 900)]))
    lk = cluster_addresses(s)
    g = contract(s, [0], lk)
    assert lk["a"] in g.vertices and lk["b"] == lk["a"]
    assert g.vertices[lk["a"]]["coins"] == {"a", "b"}


def test_parallel_transfers_fold_into_one_attributed_edge():
    """Contraction yields a multigraph; the matching model wants one directed edge per
    ordered pair, with the parallel transfers folded into its attributes."""
    s = S(tx(["a"], [("x", 100), ("y", 200)]), tx(["a"], [("x", 300)]))
    lk = {"a": "A", "x": "X", "y": "X"}
    g = contract(s, [0, 1], lk)
    assert list(g.edges) == [("A", "X")]
    assert g.edges[("A", "X")] == {"transfers": 3, "value": 600}


def test_direction_is_kept():
    s = S(tx(["a"], [("x", 100)]))
    g = contract(s, [0], {"a": "A", "x": "X"})
    assert ("A", "X") in g.edges and ("X", "A") not in g.edges


def test_self_transfer_is_a_vertex_attribute_not_an_edge():
    """Change returning to its own cluster carries no relational information, so it must
    not manufacture a self-loop the matcher would read as structure."""
    g = contract(S(tx(["a"], [("b", 100)])), [0], {"a": "A", "b": "A"})
    assert g.edges == {}
    assert g.vertices["A"]["self_transfers"] == 1
    assert g.degree("A") == 0


def test_unknown_address_is_its_own_pseudonym():
    """A partial clustering is the premise, so an address outside the lookup is a singleton
    pseudonym rather than an error."""
    g = contract(S(tx(["a"], [("x", 100)])), [0], {})
    assert set(g.vertices) == {"a", "x"}


def test_min_value_drops_dust_edges():
    s = S(tx(["a"], [("x", 1), ("y", 100_000)]))
    g = contract(s, [0], {"a": "A", "x": "X", "y": "Y"}, min_value=1_000)
    assert set(g.edges) == {("A", "Y")}


def test_neighbours_span_both_directions():
    s = S(tx(["a"], [("x", 100)]), tx(["x"], [("c", 100)]))
    g = contract(s, [0, 1], {"a": "A", "x": "X", "c": "C"})
    assert g.neighbours("X") == {"A", "C"} and g.degree("X") == 2


# --- attributes -------------------------------------------------------------

def test_attribute_is_a_lift_over_the_view_base_rate():
    """A vertex that looks exactly like its view reads 1.0. The normalisation is what makes
    the value comparable to a vertex measured in a different view, where a global covariate
    has shifted every base rate together."""
    s = S(tx(["a"], [("x", 1)], version=2), tx(["b"], [("y", 1)], version=2),
          tx(["c"], [("z", 1)], version=1))
    g = contract(s, [0, 1, 2], {})
    assert g.base_rates["version"] == {"v2": 2, "v1": 1}
    assert g.attribute("a", "version") == {"v2": 1 / (2 / 3)}
    assert g.attribute("c", "version") == {"v1": 1 / (1 / 3)}


def test_attribute_of_an_unseen_axis_is_empty_not_an_error():
    g = contract(S(tx(["a"], [("x", 1)])), [0], {})
    g.vertices["a"]["axes"]["version"] = type(g.base_rates["version"])()
    assert g.attribute("a", "version") == {}


def test_every_axis_is_populated():
    g = contract(S(tx(["a"], [("x", 1)])), [0], {})
    assert all(sum(g.base_rates[axis].values()) for axis in AXES)
    assert not g.skipped


def test_an_axis_that_cannot_be_read_is_counted_not_swallowed():
    """An extractor raising on a partial transaction is abstention, not a bug — but an axis
    that dies on every transaction would otherwise leave an empty distribution and no trace
    of why."""
    t = tx(["a"], [("x", 1)])
    for v in t["vin"]:
        del v["txid"]                               # BIP-69 ordering needs the prevout txid
    g = contract(S(t), [0], {})
    assert g.skipped["input_order"] == 1
    assert sum(g.base_rates["version"].values()) == 1

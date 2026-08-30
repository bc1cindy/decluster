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


def test_ambiguity_cut_removes_the_dense_core_and_returns_the_components_it_leaves():
    """Two otherwise separate neighbourhoods joined only through a busy hub. Cutting the hub
    is what lets them come out as two views; keeping it would leave one component."""
    from decluster.views import ambiguity_partition
    left = [tx(["l1"], [("l2", 1)]), tx(["l2"], [("l3", 1)])]
    right = [tx(["r1"], [("r2", 1)]), tx(["r2"], [("r3", 1)])]
    via_hub = [tx(["l3"], [("hub", 1)]), tx(["hub"], [("r1", 1)]),
               tx(["hub"], [("l1", 1)]), tx(["hub"], [("r3", 1)])]
    s = S(*(left + right + via_hub))
    parts = ambiguity_partition(iter(s), iter(s), core_frac=0.1)
    assert len(parts) == 2
    flat = sorted(sum(parts, []))
    assert all(i < 4 for i in flat)                     # every hub transaction was cut
    assert {tuple(sorted(p)) for p in parts} == {(0, 1), (2, 3)}


def test_ambiguity_cut_on_an_empty_sample_returns_empty_views():
    from decluster.views import ambiguity_partition
    assert ambiguity_partition(iter([]), iter([])) == [[], []]


def test_unknown_scheme_is_rejected():
    with pytest.raises(ValueError):
        partition_coins(S(tx(["a"], [("x", 1)])), "by_vibes")


# --- contraction ------------------------------------------------------------

def test_cluster_members_fuse_into_one_vertex():
    s = S(tx(["a", "b"], [("x", 900)]))
    lk = cluster_addresses(s)
    g = contract(s, [0], lk)
    assert lk["a"] in g.vertices and lk["b"] == lk["a"]
    assert g.vertices[lk["a"]]["coins"] == 2


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


def test_axes_can_be_skipped_for_a_structure_only_run():
    """The attribute counters dominate the vertex record; a wide view may only have room
    for the structure the matcher actually propagates along."""
    s = S(tx(["a"], [("x", 100)]))
    g = contract(s, [0], {}, axes=False)
    assert g.edges and not any(sum(g.base_rates[ax].values()) for ax in AXES)
    assert g.attribute("a", "version") == {}


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


# --- degree pre-filter ------------------------------------------------------

def test_transfer_counts_bound_the_degree():
    """Distinct degree is at most the transfer count, which is what makes the cheap count
    safe as a pre-filter: it never drops a vertex that degree would have kept."""
    from decluster.views import transfer_counts
    s = S(tx(["a"], [("x", 100), ("x", 200), ("y", 300)]))
    counts = transfer_counts(s)
    g = contract(s, [0], {})
    assert counts["a"] == 3 and g.degree("a") == 2
    assert all(counts[v] >= g.degree(v) for v in g.vertices)


def test_keep_drops_edges_with_an_excluded_endpoint():
    s = S(tx(["a"], [("x", 100), ("y", 100)]))
    g = contract(s, [0], {}, keep={"a", "x"})
    assert set(g.edges) == {("a", "x")}
    assert "y" not in g.vertices


def test_filtering_leaves_does_not_change_what_the_matcher_finds():
    """The pre-filter is only legitimate if it is invisible to the result: a vertex below
    degree two can neither be matched (no neighbourhood to discriminate on) nor bridge two
    others, and contributes nothing to scoring while unmatched."""
    from decluster.views import transfer_counts
    from decluster.view_match import ViewMatcher
    core = [("c1", "c2"), ("c2", "c3"), ("c3", "c4"), ("c4", "c1"), ("c1", "c3")]
    leaves = [("c1", "l1"), ("c2", "l2"), ("c3", "l3")]
    s = S(*[tx([a], [(b, 1000)]) for a, b in core + leaves])
    t = S(*[tx([a + "*"], [(b + "*", 1000)]) for a, b in core + leaves])

    full_a, full_b = contract(s, range(len(s)), {}), contract(t, range(len(t)), {})
    keep_a = {v for v, n in transfer_counts(s).items() if n >= 2}
    keep_b = {v for v, n in transfer_counts(t).items() if n >= 2}
    lean_a = contract(s, range(len(s)), {}, keep=keep_a)
    lean_b = contract(t, range(len(t)), {}, keep=keep_b)

    assert len(lean_a.vertices) < len(full_a.vertices)
    m = ViewMatcher(theta=0.0)
    seed_full = {"c1": "c1*", "c2": "c2*"}
    on_full = m.match(full_a, full_b, seed_full)
    on_lean = m.match(lean_a, lean_b, seed_full)
    assert {k: v for k, v in on_full.items() if k in lean_a.vertices} == on_lean


# --- refusing to apply CIOH blindly -----------------------------------------

def vtx(in_vals, out_vals, addrs=None, height=100):
    """A transaction carrying real values, so the de-mix and coinjoin-shape rules can fire."""
    addrs = addrs or [f"i{n}" for n in range(len(in_vals))]
    return {"txid": f"t{height}", "height": height, "version": 2, "locktime": 0,
            "fee": 100, "weight": 400,
            "vin": [{"txid": f"p{a}", "vout": 0, "sequence": 0xFFFFFFFF,
                     "prevout": {"value": v, "scriptpubkey_type": "v0_p2wpkh",
                                 "scriptpubkey_address": a}}
                    for a, v in zip(addrs, in_vals)],
            "vout": [{"value": v, "scriptpubkey_type": "v0_p2wpkh",
                      "scriptpubkey_address": f"o{n}"} for n, v in enumerate(out_vals)]}


# mix 100000 seen three times; input i = mix + change - fee, so each input resolves to one change
DEMIX_INS = [104_500, 106_500]
DEMIX_OUTS = [100_000, 100_000, 100_000, 5_000, 7_000]


def test_demix_merges_within_a_participant_and_refuses_across():
    s = S(vtx(DEMIX_INS, DEMIX_OUTS, ["a", "b"]))
    assert cluster_addresses(s, refuse=False).get("a") == cluster_addresses(
        s, refuse=False).get("b")                       # naive CIOH merges them
    lk = cluster_addresses(s, refuse=True)
    assert lk.get("a") != lk.get("b") or not lk         # refusal keeps them apart


def test_an_input_the_demix_cannot_resolve_merges_with_nobody():
    """Under refusal an unresolved input is unknown ownership, not shared ownership."""
    s = S(vtx(DEMIX_INS + [50_000], DEMIX_OUTS, ["a", "b", "c"]))
    lk = cluster_addresses(s, refuse=True)
    assert lk.get("c") is None or (lk.get("c") != lk.get("a") and lk.get("c") != lk.get("b"))


def test_coinjoin_shape_declines_cioh_entirely():
    n = 20
    s = S(vtx([10_000] * n, [9_000] * n, [f"cj{i}" for i in range(n)]))
    assert cluster_addresses(s, refuse=True) == {}
    assert len(set(cluster_addresses(s, refuse=False).values())) == 1


def test_an_ordinary_co_spend_still_merges_under_refusal():
    s = S(vtx([10_000, 20_000], [25_000, 4_000], ["a", "b"]))
    lk = cluster_addresses(s, refuse=True)
    assert lk["a"] == lk["b"]


# --- deliberately incomplete clustering -------------------------------------

def test_splitting_produces_two_pseudonyms_that_trace_to_one_cluster():
    """The premise is an incomplete clustering: one user, several pseudonyms. A matcher run
    against a clustering contracted from itself can only recover the identity map, which is
    not new information; splitting creates the object the matching is for."""
    import random
    from decluster.views import split_clusters
    lookup = {f"a{i}": "C" for i in range(10)}
    out, origin = split_clusters(lookup, frac=1.0, rng=random.Random(0))
    tags = set(out.values())
    assert len(tags) == 2
    assert all(origin[t] == "C" for t in tags)
    assert sorted(out) == sorted(lookup)                 # every address still placed


def test_splitting_leaves_singletons_and_unselected_clusters_alone():
    import random
    from decluster.views import split_clusters
    lookup = {"a": "A", "b": "A", "solo": "S"}
    out, origin = split_clusters(lookup, frac=0.0, rng=random.Random(0))
    assert out == lookup and origin == {"A": "A", "S": "S"}
    out, _ = split_clusters({"solo": "S"}, frac=1.0, rng=random.Random(0))
    assert out == {"solo": "S"}                          # nothing to split below min_size


def test_splitting_along_the_view_boundary_puts_one_pseudonym_on_each_side():
    """Random splitting leaves both halves in both views, so the matcher can take the
    identity match and never attempt the rejoin. Splitting on the boundary removes that
    escape: the discovery becomes the only correspondence available."""
    import random
    from decluster.views import split_clusters_by_view
    lookup = {"a1": "C", "a2": "C", "b1": "C", "b2": "C", "solo": "S"}
    out, origin = split_clusters_by_view(lookup, {"a1", "a2", "solo"}, frac=1.0,
                                         rng=random.Random(0))
    assert out["a1"] == out["a2"] == "C#a"
    assert out["b1"] == out["b2"] == "C#b"
    assert origin["C#a"] == origin["C#b"] == "C"
    assert out["solo"] == "S"                    # wholly on one side: nothing to split


def test_a_cluster_confined_to_one_view_is_left_whole():
    import random
    from decluster.views import split_clusters_by_view
    lookup = {"a1": "C", "a2": "C"}
    out, origin = split_clusters_by_view(lookup, {"a1", "a2"}, frac=1.0,
                                         rng=random.Random(0))
    assert out == lookup and origin == {"C": "C"}


def test_a_transaction_funded_by_several_pseudonyms_asserts_no_edges():
    """An edge is a transfer from one cluster to another. Where several pseudonyms fund a
    transaction, which of them paid which output is exactly what is unobservable, and
    asserting every pair invents relationships — in a coinjoin, the one relationship the
    construction is defined not to have."""
    s = S(vtx([10_000, 20_000], [15_000, 14_000], ["a", "b"]))
    g = contract(s, [0], {"a": "A", "b": "B"})       # two distinct source pseudonyms
    assert g.edges == {}
    assert g.unattributed == 1
    assert set(g.vertices) >= {"A", "B"}             # the vertices still exist

    merged = contract(s, [0], {"a": "A", "b": "A"})  # one owner: attributable again
    assert merged.edges and merged.unattributed == 0


def test_max_sources_can_be_raised_deliberately():
    s = S(vtx([10_000, 20_000], [15_000, 14_000], ["a", "b"]))
    g = contract(s, [0], {"a": "A", "b": "B"}, max_sources=2)
    assert len(g.edges) == 4 and g.unattributed == 0

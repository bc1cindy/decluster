import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from decluster.contraction import AXES, PseudonymGraph, contract
from decluster.view_partition import height_bands, partition_coins
from decluster.views import cluster_addresses
from decluster.contraction import contract_degrees as views_contract_degrees


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
    from decluster.view_partition import ambiguity_partition
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
    from decluster.view_partition import ambiguity_partition
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
    assert g.edges[("A", "X")]["transfers"] == 3
    assert g.edges[("A", "X")]["value"] == 600


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


def test_self_transfer_keeps_its_value_and_span():
    """The loop stays out of the structure, but it is still a labelled edge of the user
    network, so contracting it must not drop the value and time it carries."""
    s = S(tx(["a"], [("b", 100)], height=10), tx(["b"], [("c", 250)], height=40))
    g = contract(s, [0, 1], {"a": "A", "b": "A", "c": "A"})
    assert g.edges == {}
    assert g.self_edges == {"A": {"transfers": 2, "value": 350, "first": 10, "last": 40}}


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
    from decluster.contraction import transfer_counts
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
    from decluster.contraction import transfer_counts
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
    from decluster.views import split_clusters_by_view, view_lookup
    lookup = {"a1": "C", "a2": "C", "b1": "C", "b2": "C", "solo": "S"}
    split_cids, origin = split_clusters_by_view(lookup, {"a1", "a2", "solo"}, frac=1.0,
                                                rng=random.Random(0))
    assert split_cids == {"C"}
    la = view_lookup(lookup, split_cids, "#a")
    lb = view_lookup(lookup, split_cids, "#b")
    assert la.get("a1") == la.get("b1") == "C#a"
    assert lb.get("a1") == lb.get("b1") == "C#b"
    assert origin["C#a"] == origin["C#b"] == "C"
    assert la.get("solo") == lb.get("solo") == "S"   # wholly on one side: nothing to split
    assert la.get("unknown", "unknown") == "unknown"  # absent addresses stay singletons


def test_an_address_used_in_both_windows_does_not_carry_its_tag_into_the_other_view():
    """The rejoin is the only correspondence on offer only if each view holds one side of
    the split. Tagging by where an address is first seen leaves a both-windows address
    marked #a everywhere, so view B holds C#a as well as C#b and the identity match — the
    structurally better one — is available and graded wrong."""
    import random
    from decluster.views import split_clusters_by_view, view_lookup
    lookup = {"shared": "C", "b_only": "C", "q": "Q"}
    split_cids, _ = split_clusters_by_view(lookup, {"shared"}, frac=1.0,
                                           rng=random.Random(0))
    window_b = S(tx(["shared"], [("q", 5000)]), tx(["b_only"], [("q", 5000)]))
    gb = contract(window_b, lookup=view_lookup(lookup, split_cids, "#b"), axes=False)
    assert "C#a" not in set(gb.vertices)
    assert "C#b" in set(gb.vertices)


def test_a_cluster_confined_to_one_view_is_left_whole():
    import random
    from decluster.views import split_clusters_by_view, view_lookup
    lookup = {"a1": "C", "a2": "C"}
    split_cids, origin = split_clusters_by_view(lookup, {"a1", "a2"}, frac=1.0,
                                                rng=random.Random(0))
    assert split_cids == set() and origin == {"C": "C"}
    assert view_lookup(lookup, split_cids, "#a").get("a1") == "C"


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


def test_keep_drops_edges_and_never_invents_one():
    """`keep` is a view restriction, not a re-attribution. Applying it before the
    max_sources bound would let a transaction the contraction refused emit an edge as soon
    as the filter left it a single source — and the survivor is systematically the hub."""
    s = S(tx(["a", "b", "c"], [("x", 5000)]))
    lookup = {"a": "A", "b": "B", "c": "C", "x": "X"}
    assert contract(s, lookup=lookup, axes=False).edges == {}
    filtered = contract(s, lookup=lookup, axes=False, keep={"A", "X"})
    assert filtered.edges == {}
    assert filtered.unattributed == 1


def test_max_sources_can_be_raised_deliberately():
    s = S(vtx([10_000, 20_000], [15_000, 14_000], ["a", "b"]))
    g = contract(s, [0], {"a": "A", "b": "B"}, max_sources=2)
    assert len(g.edges) == 4 and g.unattributed == 0


def _tx(ins, outs, height=0):
    return ({"height": height,
             "vin": [{"prevout": {"scriptpubkey_address": a}} for a in ins],
             "vout": [{"scriptpubkey_address": a} for a in outs]}, 0)


def test_decore_partition_yields_overlapping_views_unlike_ambiguity_cut():
    """The reformulated ambiguity-cut: de-core then split on an orthogonal axis (height), so an
    entity active on both sides appears in BOTH views. Contrast with ambiguity_partition, whose
    connected components are vertex-disjoint."""
    from decluster.tx_addrs import in_addrs, out_addrs
    from decluster.view_partition import ambiguity_partition, decore_partition
    # HUB is the busiest address -> the dense core; a1 is active in both height windows
    s = ([_tx(["HUB"], [f"h{i}"], height=i) for i in range(20)]
         + [_tx(["a1"], ["x1"], height=1), _tx(["a1"], ["x2"], height=100),
            _tx(["b1"], ["y1"], height=1), _tx(["c1"], ["z1"], height=100),
            _tx(["a1", "HUB"], ["core_out"], height=50)])  # core-touching -> dropped from both

    def addrs(idxs):
        out = set()
        for i in idxs:
            out |= set(in_addrs(s[i][0])) | {a for a, _ in out_addrs(s[i][0])}
        return out

    views = decore_partition(s, core_frac=0.02, scheme="epoch")
    assert len(views) == 2 and all(views)
    va, vb = addrs(views[0]), addrs(views[1])
    assert "a1" in (va & vb)                 # the recurring entity appears in both views
    assert "HUB" not in (va | vb)            # the core is removed from both
    # ambiguity_partition on the same sample: its top-2 components share no address
    comps = ambiguity_partition(iter(s), iter(s), core_frac=0.02)
    if len(comps) >= 2 and all(comps):
        assert not (addrs(comps[0]) & addrs(comps[1]))


def test_transfer_counts_skips_multi_source_without_raising():
    """Regression: a multi-source tx must not raise NameError (the old `g.unattributed` bug)."""
    from decluster.contraction import transfer_counts
    s = [_tx(["p", "q"], ["out"])]           # 2 distinct source pseudonyms, max_sources=1
    counts = transfer_counts(s, lookup={}, max_sources=1)   # must not raise
    assert counts == {} or isinstance(counts, dict)


def test_contract_degrees_matches_the_graph_it_avoids_building():
    """The degree-only pass exists to skip the throwaway first contraction, so it has to agree
    with it everywhere — isolated vertices and unattributable transactions included."""
    s = S(tx(["a"], [("x", 5000)]),
          tx(["x"], [("y", 4000)]),
          tx(["b", "c"], [("z", 3000)]),      # two sources: unattributable, no edges
          tx(["y"], [("y", 3000)]))           # self-transfer: not a degree
    lookup = {"a": "A", "x": "X", "y": "Y", "b": "B", "c": "C", "z": "Z"}
    full = contract(s, lookup=lookup, axes=False)
    expected = {v: full.degree(v) for v in full.vertices}
    assert views_contract_degrees(s, lookup=lookup) == expected


def test_structure_only_contraction_allocates_no_axis_counters():
    """The per-axis Counters are the vertex record's bulk; a matcher run that uses structure
    alone must not pay for them."""
    s = S(tx(["a"], [("x", 5000)]))
    assert "axes" not in contract(s, axes=False).vertices["a"]
    assert "axes" in contract(s, axes=True).vertices["a"]


def test_asking_for_a_degree_does_not_create_the_vertex():
    """A full degree sweep asks about every vertex; indexing the adjacency defaultdict would
    leave an empty set behind for each one."""
    g = contract(S(tx(["a"], [("x", 5000)])), axes=False)
    assert g.degree("never_seen") == 0
    assert "never_seen" not in g._out and "never_seen" not in g._in


# --- collapse cut -----------------------------------------------------------

def test_collapse_boundary_cuts_the_merge_of_two_substantial_clusters():
    """The cut the framework asks for is the cluster-collapse event, not the busiest address. A
    merge that grows one cluster by a fresh address is not a collapse; a merge that joins two
    established clusters is."""
    from decluster.view_partition import collapse_boundary
    s = S(tx(["a1", "a2"], [("x", 1)]),      # builds cluster A  (not a collapse: both fresh)
          tx(["b1", "b2"], [("y", 1)]),      # builds cluster B  (not a collapse)
          tx(["a1", "a3"], [("z", 1)]),      # extends A by a fresh address -> not a collapse
          tx(["a1", "b1"], [("w", 1)]))      # joins A and B     -> THE collapse
    boundary, uf = collapse_boundary(s, min_side=2)
    assert boundary == [3]
    assert uf.find("a1") == uf.find("a3")            # A stayed whole
    assert uf.find("a1") != uf.find("b1")            # the declined merge really was declined


def test_a_fresh_address_joining_one_cluster_is_never_a_collapse():
    from decluster.view_partition import collapse_boundary
    s = S(tx(["a1", "a2"], [("x", 1)]), tx(["a1", "a2", "a3", "a4"], [("y", 1)]))
    assert collapse_boundary(s, min_side=2)[0] == []


def test_collapse_partition_removes_the_boundary_and_splits_the_rest_by_height():
    """Cut for ambiguity, split for overlap: taking the components the cut leaves would give
    views that share no entity, so the survivors are split on an orthogonal axis."""
    from decluster.view_partition import collapse_partition
    s = S(tx(["a1", "a2"], [("x", 1)], height=10),
          tx(["b1", "b2"], [("y", 1)], height=20),
          tx(["a1", "b1"], [("w", 1)], height=30),      # collapse -> in no view
          tx(["a1"], [("z", 1)], height=90))
    parts = collapse_partition(s, min_side=2)
    assert len(parts) == 2
    flat = sorted(sum(parts, []))
    assert 2 not in flat                                # the boundary is in no view
    assert flat == [0, 1, 3]


def test_collapse_partition_generalises_beyond_two_views():
    from decluster.view_partition import collapse_partition
    s = S(*[tx([f"u{i}"], [(f"o{i}", 1)], height=10 * i) for i in range(1, 10)])
    parts = collapse_partition(s, n_views=3)
    assert len(parts) == 3
    assert sorted(sum(parts, [])) == list(range(9))     # nothing lost, nothing duplicated


def test_an_edge_carries_the_height_span_of_the_transfers_it_folds():
    """Reid and Harrigan label every user-network edge with value and time. Folding parallel
    transfers into one edge throws the time away unless the span is kept, and the span is what
    separates a relationship that recurs from one that fired once."""
    s = S(tx(["a"], [("x", 100)], height=100),
          tx(["a"], [("x", 200)], height=140),
          tx(["a"], [("x", 300)], height=120))
    e = contract(s, lookup={"a": "A", "x": "X"}, axes=False).edges[("A", "X")]
    assert e["transfers"] == 3 and e["value"] == 600
    assert (e["first"], e["last"]) == (100, 140)


def test_a_single_transfer_edge_has_a_zero_width_span():
    s = S(tx(["a"], [("x", 100)], height=77))
    e = contract(s, lookup={"a": "A", "x": "X"}, axes=False).edges[("A", "X")]
    assert e["first"] == e["last"] == 77


# --- conspicuousness ordering ------------------------------------------------

def vtx_typed(in_vals, out_vals, addrs, types=None, height=100):
    """A transaction carrying the input values and script types a merge ranking needs."""
    types = types or ["v0_p2wpkh"] * len(in_vals)
    return {"txid": f"t{addrs}", "height": height, "version": 2, "locktime": 0,
            "fee": 100, "weight": 400,
            "vin": [{"txid": f"p{a}", "vout": 0, "sequence": 0xFFFFFFFF,
                     "prevout": {"value": v, "scriptpubkey_type": t,
                                 "scriptpubkey_address": a}}
                    for a, v, t in zip(addrs, in_vals, types)],
            "vout": [{"value": v, "scriptpubkey_type": "v0_p2wpkh",
                      "scriptpubkey_address": f"o{i}"} for i, v in enumerate(out_vals)]}


def test_a_transaction_that_argues_against_itself_is_less_conspicuous():
    from decluster.views import merge_objections
    # neither tell fires: one owner is the plain reading
    assert merge_objections(vtx_typed([40_000, 50_000], [70_000, 19_000], ["a", "b"])) == 0
    # an input alone already covers the largest output -> the others were unnecessary
    assert merge_objections(vtx_typed([90_000, 10_000], [60_000, 39_000], ["a", "b"])) == 1
    # inputs disagree on script type -> more than one plausible contributor
    assert merge_objections(
        vtx_typed([40_000, 50_000], [70_000, 19_000], ["a", "b"],
                  types=["v0_p2wpkh", "p2pkh"])) == 1
    # both
    assert merge_objections(
        vtx_typed([90_000, 10_000], [60_000, 39_000], ["a", "b"],
                  types=["v0_p2wpkh", "p2pkh"])) == 2


def test_a_single_input_transaction_has_nothing_to_argue_about():
    from decluster.views import merge_objections
    assert merge_objections(vtx_typed([90_000], [89_000], ["a"])) == 0


def test_an_address_only_transaction_cannot_be_ranked():
    """Absence of evidence is not absence of objection: reading it as zero would put every
    transaction of an address-only export into the conspicuous tier for free."""
    from decluster.views import merge_objections, merge_order

    def addr_only(ins, outs):                      # what the graph exports actually carry
        return {"txid": f"t{ins}", "height": 100,
                "vin": [{"prevout": {"scriptpubkey_address": a}} for a in ins],
                "vout": [{"scriptpubkey_address": a} for a in outs]}

    assert merge_objections(addr_only(["a", "b"], ["x"])) is None
    with pytest.raises(ValueError, match="address-only"):
        merge_order(S(addr_only(["a", "b"], ["x"]), addr_only(["c", "d"], ["y"])))

    # single-input transactions score zero for free, so they must not make the export look
    # rankable — an unrankable sample stays unrankable however many of them it carries
    with pytest.raises(ValueError, match="address-only"):
        merge_order(S(addr_only(["a"], ["x"]), addr_only(["b", "c"], ["y"]),
                      addr_only(["d"], ["z"])))


def test_staging_clusters_the_conspicuous_transactions_first():
    from decluster.views import merge_order
    doubtful = vtx_typed([90_000, 10_000], [60_000, 39_000], ["a", "b"], height=10)
    clean = vtx_typed([40_000, 50_000], [70_000, 19_000], ["c", "d"], height=20)
    order = merge_order(S(doubtful, clean))
    assert order == [1, 0]                       # block order was doubtful-first; staging inverts


def test_staging_leaves_the_partition_reachable_by_either_order_alone():
    """Ordering changes which merges are judged against which context, not what a merge means."""
    from decluster.views import cluster_addresses
    s = S(vtx_typed([40_000, 50_000], [70_000, 19_000], ["a", "b"], height=10),
          vtx_typed([40_000, 50_000], [70_000, 19_000], ["b", "c"], height=20))
    plain = cluster_addresses(s, refuse=False)
    ordered = cluster_addresses(s, refuse=False, staged=True)
    assert {frozenset(g) for g in _groups(plain)} == {frozenset(g) for g in _groups(ordered)}


def test_staging_leaves_the_partition_alone_under_change_linking_too():
    """The change link is the one decision that reads the partition built so far, so it is where
    the order could leak into the result. A doubtful merge of a,b followed by a clean spend of
    a,b with fresh optimal change: in sample order the spend sees a,b already joined and the
    change attaches, and staging must not take that away by running the clean spend first."""
    from decluster.views import cluster_addresses

    def vtx_out(in_vals, out_pairs, addrs, height=100):
        t = vtx_typed(in_vals, [v for _, v in out_pairs], addrs, height=height)
        for o, (addr, _) in zip(t["vout"], out_pairs):
            o["scriptpubkey_address"] = addr
        return t

    doubtful = vtx_out([90_000, 10_000], [("pay0", 60_000), ("out0", 39_000)], ["a", "b"], height=10)
    clean = vtx_out([40_000, 50_000], [("pay1", 70_000), ("chg", 19_000)], ["a", "b"], height=20)
    s = S(doubtful, clean)
    plain = cluster_addresses(s, change_link=True)
    ordered = cluster_addresses(s, change_link=True, staged=True)
    assert {frozenset(g) for g in _groups(plain)} == {frozenset(g) for g in _groups(ordered)}
    assert plain["chg"] == plain["a"] == plain["b"]


def _groups(lookup):
    out = {}
    for addr, cid in lookup.items():
        out.setdefault(cid, []).append(addr)
    return out.values()


def test_every_scheme_honours_the_view_count():
    """The framework asks for the n > 2 generalisation of every cut, not of two of them.

    `epoch` and `decore` used to halve the height range whatever `n_views` said, so a caller
    asking for four views got two and was told nothing.
    """
    sample = [({"txid": f"t{i}", "height": 800000 + i,
                "vin": [{"prevout": {"scriptpubkey_address": f"a{i}"}}],
                "vout": [{"scriptpubkey_address": f"b{i}", "value": 1000}]}, 0)
              for i in range(40)]
    for scheme in ("epoch", "decore", "collapse"):
        for n in (2, 3, 4):
            parts = partition_coins(sample, scheme=scheme, n_views=n)
            assert len(parts) == n, f"{scheme} returned {len(parts)} views for n_views={n}"


def test_the_bands_cover_the_range_without_overlap():
    bounds = height_bands([800000, 800001, 800009], 3)
    assert bounds[0][0] == 800000 and bounds[-1][1] == 800009
    for (_, top), (bottom, _) in zip(bounds, bounds[1:]):
        assert bottom == top + 1


def test_a_view_count_below_one_is_refused():
    with pytest.raises(ValueError, match="at least 1"):
        height_bands([1, 2, 3], 0)

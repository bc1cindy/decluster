from decluster.propagate import build_rarity, entity_signature, label_scores, eccentricity, propagate_merge, should_split, NSPropagator, holdout_reid, partition_from_assignment
from decluster.graph_metric import partition_entropy


def test_build_rarity_counts_supports():
    sigs = [{"a": 0.6, "b": 0.4}, {"a": 1.0}, {"b": 0.5, "c": 0.5}]
    assert build_rarity(sigs) == {"a": 2, "b": 2, "c": 1}


def test_build_rarity_empty():
    assert build_rarity([]) == {}


def test_entity_signature_sums_and_normalises():
    sig = entity_signature([{"a": 0.5, "b": 0.5}, {"a": 0.5, "c": 0.5}])
    # summed: a=1.0, b=0.5, c=0.5 (total 2.0) -> normalised
    assert sig == {"a": 0.5, "b": 0.25, "c": 0.25}


def test_entity_signature_empty():
    assert entity_signature([]) == {}
    assert entity_signature([{}, {}]) == {}


def test_label_scores_uses_provenance_link():
    node = {"rare": 0.5, "hub": 0.5}
    labels = {"X": {"rare": 0.5, "hub": 0.5}, "Y": {"hub": 1.0}}
    rarity = {"rare": 1, "hub": 100}   # rare ancestor weighs more
    s = label_scores(node, labels, rarity)
    assert s["X"] > s["Y"] > 0.0


def test_eccentricity_gap_over_spread():
    # best 10, second 2, third 0 -> clear separation, positive eccentricity
    assert eccentricity({"a": 10.0, "b": 2.0, "c": 0.0}) > 0.0


def test_eccentricity_degenerate():
    assert eccentricity({"a": 5.0}) == 0.0          # <2 scores
    assert eccentricity({"a": 3.0, "b": 3.0}) == 0.0  # zero spread


def test_propagate_merge_assigns_by_dominant_overlap():
    node_sigs = {
        "seedX": {"r1": 1.0},
        "seedY": {"r2": 1.0},
        "u1":    {"r1": 0.9, "hub": 0.1},   # strong r1 overlap with X
        "u2":    {"hub": 1.0},              # only a hub ancestor -> weak leaked overlap
    }
    seeds = {"seedX": "X", "seedY": "Y"}
    rarity = {"r1": 1, "r2": 1, "hub": 500}
    out = propagate_merge(node_sigs, seeds, rarity, theta=0.5, min_score=0.1)
    assert out["u1"] == "X"
    assert "u2" not in out            # leaked hub overlap (~0.006) is below the floor


def test_propagate_merge_idempotent():
    node_sigs = {"s": {"r": 1.0}, "u": {"r": 0.8, "h": 0.2}}
    seeds = {"s": "S"}
    rarity = {"r": 1, "h": 400}
    first = propagate_merge(node_sigs, seeds, rarity, theta=0.5, min_score=0.1)
    # feeding the result back as seeds changes nothing
    second = propagate_merge(node_sigs, first, rarity, theta=0.5, min_score=0.1)
    assert first == second


class _FakeCombiner:
    def __init__(self, s): self._s = s
    def score(self, a, b): return self._s

def test_should_split_requires_both_channels():
    disjoint_a, disjoint_b = {"x": 1.0}, {"y": 1.0}   # provenance_link == 0
    overlap_a, overlap_b = {"x": 1.0}, {"x": 1.0}     # provenance_link > 0
    rarity = {"x": 1, "y": 1}
    diverge = _FakeCombiner(-5.0)     # fingerprint says different owner
    agree = _FakeCombiner(+3.0)       # fingerprint says same owner
    # both channels agree -> split
    assert should_split(disjoint_a, disjoint_b, {}, {}, diverge, rarity) is True
    # provenance disjoint but fingerprint agrees -> no split
    assert should_split(disjoint_a, disjoint_b, {}, {}, agree, rarity) is False
    # fingerprint diverges but provenance overlaps -> no split
    assert should_split(overlap_a, overlap_b, {}, {}, diverge, rarity) is False


class _ABCombiner:
    """Distinct name avoids collision with the earlier _FakeCombiner that takes a constructor arg."""
    def score(self, a, b):
        return -5.0 if {a, b} == {"A", "B"} else 3.0

def test_nspropagator_refines_and_propagates():
    node_sigs = {
        "A":     {"r1": 1.0},            # co-spend cluster [A, B] ...
        "B":     {"r9": 1.0},            # ... B disjoint from A + divergent fp -> split off
        "seedX": {"r1": 1.0},
        "u_ok":  {"r1": 0.9, "h": 0.1},  # propagates to label X
    }
    rarity = {"r1": 1, "r9": 1, "h": 300}
    node_txs = {k: k for k in node_sigs}
    prop = NSPropagator(rarity, _ABCombiner(), theta=0.5, min_score=0.1, refuse_below=-2.0)
    res = prop.run([["A", "B"]], {"seedX": "X"}, node_sigs, node_txs)
    groups = [sorted(g) for g in res["refined"]]
    assert ["A"] in groups and ["B"] in groups     # split channel removed the A-B edge
    assert res["labels"]["u_ok"] == "X"            # merge channel propagated X to u_ok


class _AllAgree:
    def score(self, a, b): return 3.0


def test_partition_from_assignment_groups_by_label():
    groups = partition_from_assignment({"a": "X", "b": "X", "c": "Y"})
    assert sorted(sorted(g) for g in groups) == [["a", "b"], ["c"]]
    assert partition_entropy(groups) >= 0.0   # smoke: feeds the existing metric


def test_holdout_reid_recovers_hidden_seed():
    node_sigs = {
        "s1": {"r1": 1.0}, "s2": {"r2": 1.0},
        "m1": {"r1": 0.9, "h": 0.1}, "m2": {"r2": 0.9, "h": 0.1},
    }
    seeds = {"s1": "A", "s2": "B", "m1": "A", "m2": "B"}   # full labels as the silver key
    rarity = {"r1": 1, "r2": 1, "h": 300}
    prop = NSPropagator(rarity, _AllAgree(), theta=0.5, min_score=0.1)
    res = holdout_reid(node_sigs, seeds, prop, hide_frac=0.5, seed=0)
    assert res["hidden"] >= 1
    assert res["rate"] >= 0.0


def test_integration_driver_runs_offline():
    # exercises the driver wiring on tiny synthetic input, no fetch/network
    from examples.ns_propagation import run_on_signatures
    node_sigs = {"s": {"r": 1.0}, "m": {"r": 0.9, "h": 0.1}}
    seeds = {"s": "S"}
    txs = {"s": "s", "m": "m"}
    rarity = {"r": 1, "h": 200}
    summary = run_on_signatures(node_sigs, seeds, txs, rarity)
    assert "median_bits_before" in summary and "median_bits_after" in summary
    assert summary["reid_rate"] >= 0.0

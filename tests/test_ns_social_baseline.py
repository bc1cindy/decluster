import random

import pytest

from decluster.baselines.narayanan_shmatikov import (
    _sparse_match_scores,
    _sparse_winner,
    _winner,
    conservative_revisit,
    eccentricity,
    evaluate,
    match_scores,
    propagate,
)
from decluster.contraction import PseudonymGraph


def graph(vertices, edges):
    result = PseudonymGraph()
    for vertex in vertices:
        result._vertex(vertex)
    for source, target in edges:
        result.edges[(source, target)] = {"transfers": 1, "value": 1}
        result._out[source].add(target)
        result._in[target].add(source)
    return result


def two_views(*, n=80, edge_probability=0.12, keep_probability=0.86, seed=7):
    """Independently perturb two relabelled views of one planted directed graph."""
    rng = random.Random(seed)
    vertices = list(range(n))
    underlying = [(u, v) for u in vertices for v in vertices
                  if u != v and rng.random() < edge_probability]
    left_edges = [edge for edge in underlying if rng.random() < keep_probability]
    right_edges = [(f"v{u}", f"v{v}") for u, v in underlying
                   if rng.random() < keep_probability]
    # Independent false edges make the views noisy rather than mere edge-deleted copies.
    for u in vertices:
        if rng.random() < 0.18:
            v = rng.choice([x for x in vertices if x != u])
            left_edges.append((u, v))
        if rng.random() < 0.18:
            v = rng.choice([x for x in vertices if x != u])
            right_edges.append((f"v{u}", f"v{v}"))
    return (graph(vertices, left_edges),
            graph([f"v{v}" for v in vertices], right_edges),
            {v: f"v{v}" for v in vertices})


def test_eccentricity_uses_the_full_score_population():
    assert eccentricity({"a": 4.0, "b": 1.0, "c": 0.0}) == pytest.approx(
        3.0 / 1.699673171197595
    )
    assert eccentricity({"a": 1.0, "b": 1.0}) == 0.0
    assert eccentricity({"a": 1.0}) == 0.0


def test_match_scores_preserves_direction_and_normalizes_candidate_degree():
    left = graph(["u", "incoming", "outgoing"],
                 [("incoming", "u"), ("u", "outgoing")])
    right = graph(["x", "i", "o", "busy"],
                  [("i", "x"), ("x", "o"), ("busy", "x")])
    scores = match_scores(left, right, {"incoming": "i", "outgoing": "o"}, "u")
    assert scores["x"] == pytest.approx(1 / (2 ** 0.5) + 1.0)


def test_two_distinct_views_propagate_from_independent_seeds_under_noise():
    left, right, truth = two_views()
    seed_nodes = list(range(16))
    seeds = {node: truth[node] for node in seed_nodes}
    result = propagate(left, right, seeds, theta=1.5)
    metrics = evaluate(result.mapping, truth, seeds)
    assert result.rounds >= 1
    assert metrics["declared"] >= 45
    assert metrics["precision"] >= 0.95
    assert metrics["coverage"] >= 0.65


def test_lower_overlap_reduces_coverage_without_forcing_guesses():
    clean_left, clean_right, truth = two_views(keep_probability=0.90, seed=19)
    noisy_left, noisy_right, _ = two_views(keep_probability=0.55, seed=19)
    seeds = {node: truth[node] for node in range(18)}
    clean = evaluate(propagate(clean_left, clean_right, seeds).mapping, truth, seeds)
    noisy = evaluate(propagate(noisy_left, noisy_right, seeds).mapping, truth, seeds)
    assert clean["coverage"] > noisy["coverage"]
    assert clean["precision"] >= 0.95
    assert noisy["precision"] is None or noisy["precision"] >= 0.90


def test_bad_or_nonexistent_seed_mapping_is_rejected():
    left, right, truth = two_views(n=10)
    with pytest.raises(ValueError, match="one-to-one"):
        propagate(left, right, {0: truth[0], 1: truth[0]})
    with pytest.raises(ValueError, match="left view"):
        propagate(left, right, {999: truth[0]})
    with pytest.raises(ValueError, match="right view"):
        propagate(left, right, {0: "absent"})


def test_conservative_revisit_preserves_seeds_bijection_and_coverage():
    left, right, truth = two_views(seed=23)
    seeds = {node: truth[node] for node in range(16)}
    base = propagate(left, right, seeds)
    revisited = propagate(left, right, seeds, conservative_revisit_rounds=5)

    assert revisited.revisit_policy == "conservative_leave_one_out"
    assert all(revisited.mapping[node] == image for node, image in seeds.items())
    assert len(revisited.mapping) == len(set(revisited.mapping.values()))
    assert set(revisited.mapping) == set(base.mapping)


def test_conservative_revisit_corrects_an_unclaimed_wrong_image():
    left = graph(["s", "t", "x", "z"], [("s", "x"), ("t", "x")])
    right = graph(["S", "T", "X", "Y"], [("S", "X"), ("T", "X")])
    seeds = {"s": "S", "t": "T"}

    result = conservative_revisit(
        left,
        right,
        {**seeds, "x": "Y"},
        seeds,
        theta=0.5,
        max_rounds=2,
    )

    assert result.mapping == {**seeds, "x": "X"}
    assert result.remapped_per_round == (1,)


def test_revisit_is_disabled_by_default_and_rejects_negative_budget():
    left, right, truth = two_views(n=10)
    result = propagate(left, right, {0: truth[0], 1: truth[1]})

    assert result.revisit_policy == "disabled"
    assert result.remapped_per_round == ()
    with pytest.raises(ValueError, match="non-negative"):
        propagate(left, right, {0: truth[0]}, conservative_revisit_rounds=-1)


def test_revisit_rejects_mapping_vertices_outside_either_view():
    left, right, truth = two_views(n=10)
    seeds = {0: truth[0]}

    with pytest.raises(ValueError, match="left view"):
        conservative_revisit(left, right, {**seeds, 999: truth[1]}, seeds)
    with pytest.raises(ValueError, match="right view"):
        conservative_revisit(left, right, {**seeds, 1: "absent"}, seeds)


def test_the_sparse_gate_propagate_runs_agrees_with_the_dense_reference():
    """`propagate` scores with `_sparse_match_scores`/`_sparse_winner`; only `match_scores`
    and `eccentricity` are checked against the paper. Pin that the two families decide the
    same way on every call a real propagation makes."""
    decisions = 0
    for fixture_seed in (7, 19, 23):
        left, right, truth = two_views(seed=fixture_seed)
        mapping = {node: truth[node] for node in range(16)}
        while True:
            accepted = 0
            for node in sorted((v for v in left.vertices if v not in mapping), key=repr):
                dense = _winner(match_scores(left, right, mapping, node), 1.5)
                sparse = _sparse_winner(*_sparse_match_scores(left, right, mapping, node), 1.5)
                assert dense == sparse
                decisions += 1
                if sparse is None:
                    continue
                reverse = {image: v for v, image in mapping.items()}
                back = _sparse_winner(
                    *_sparse_match_scores(right, left, reverse, sparse), 1.5
                )
                if back != node:
                    continue
                mapping[node] = sparse
                accepted += 1
            if not accepted:
                break
    assert decisions > 200


def test_the_two_readings_of_the_eccentricity_population_are_both_available():
    """The prose scores against the unmapped right vertices, the pseudocode against all of
    them with the claimed ones left at zero. On this fixture the wider population declares
    one vertex more; the default is the prose, which every published run used."""
    left, right, truth = two_views()
    seeds = {node: truth[node] for node in range(16)}

    prose = evaluate(propagate(left, right, seeds).mapping, truth, seeds)
    pseudocode = evaluate(
        propagate(left, right, seeds, population="all").mapping, truth, seeds
    )

    assert (prose["declared"], prose["correct"]) == (63, 63)
    assert (pseudocode["declared"], pseudocode["correct"]) == (64, 64)
    with pytest.raises(ValueError, match="population"):
        propagate(left, right, seeds, population="every")

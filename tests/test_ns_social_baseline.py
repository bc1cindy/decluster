import random

import pytest

from decluster.baselines.narayanan_shmatikov import (
    eccentricity,
    evaluate,
    match_scores,
    propagate,
)
from decluster.views import PseudonymGraph


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

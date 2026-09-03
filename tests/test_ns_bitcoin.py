import glob
import os
import random
from collections import Counter

import pytest

from decluster import reproducibility as rp
from decluster.ns_bitcoin import (SEED_INDEPENDENT, SEED_SAMPLED, eligible_correspondence,
                                  graph_overlap, run_bitcoin_views, sampled_seeds,
                                  sweep_bitcoin_views, unique_entity_seeds)
from decluster.views import PseudonymGraph
from examples.ns_bitcoin_views import (build_parser, build_views, independent_entity_labels,
                                       run_configuration, window_size)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def graph(vertices, edges):
    g = PseudonymGraph(axes=False)
    for vertex in vertices:
        g._vertex(vertex)
    for source, target in edges:
        g.edges[(source, target)] = {"transfers": 1, "value": 1}
        g._out[source].add(target)
        g._in[target].add(source)
    return g


def chain_views():
    left = graph(range(6), [(0, 2), (1, 2), (0, 3), (2, 4), (3, 5)])
    right = graph([f"r{i}" for i in range(6)],
                  [("r0", "r2"), ("r1", "r2"), ("r0", "r3"),
                   ("r2", "r4"), ("r3", "r5")])
    return left, right, {i: f"r{i}" for i in range(6)}


def path_views(n):
    """A directed path, whose neighbourhoods are asymmetric enough that misplacing the seeds
    really destroys the propagation."""
    left = graph(range(n), [(i, i + 1) for i in range(n - 1)])
    right = graph([f"r{i}" for i in range(n)],
                  [(f"r{i}", f"r{i + 1}") for i in range(n - 1)])
    return left, right, {i: f"r{i}" for i in range(n)}


def tx(height, inputs, outputs):
    return {"height": height, "txid": f"{height}-{inputs[0]}",
            "vin": [{"prevout": {"scriptpubkey_address": a}} for a in inputs],
            "vout": [{"scriptpubkey_address": a, "value": 1000} for a in outputs]}


def test_entity_seeds_require_unique_independent_labels():
    left = [("pool-a", "a"), ("pool-b", "b1"), ("pool-b", "b2")]
    right = [("pool-a", "x"), ("pool-b", "y")]
    assert unique_entity_seeds(left, right) == {"a": "x"}


def test_entity_seeds_refuse_a_right_vertex_two_entities_both_claim():
    """Two labels landing on one right vertex would return a non-injective map, which
    `propagate` rejects outright. Both are refused rather than one being kept by iteration
    order."""
    left = [("pool-a", "La"), ("pool-b", "Lb")]
    right = [("pool-a", "R1"), ("pool-b", "R1")]
    assert unique_entity_seeds(left, right) == {}


def test_entity_seeds_refuse_a_left_vertex_two_entities_both_claim():
    """The mirror case, which a dict comprehension resolves silently: one contracted cluster
    holding both a pool address and an exchange deposit address carries two entity labels, and
    keeping whichever came last would drop a label without saying so."""
    left = [("pool-a", "L1"), ("exchange", "L1")]
    right = [("pool-a", "R1"), ("exchange", "R2")]
    assert unique_entity_seeds(left, right) == {}


def test_entity_seeds_keep_the_unambiguous_labels_beside_a_refused_collision():
    left = [("pool-a", "La"), ("pool-b", "Lb"), ("exchange", "Lc")]
    right = [("pool-a", "R1"), ("pool-b", "R1"), ("exchange", "R3")]
    assert unique_entity_seeds(left, right) == {"Lc": "R3"}


def test_bitcoin_seam_reports_overlap_and_controls_without_counting_seeds():
    left, right, truth = chain_views()
    result = run_bitcoin_views(left, right, truth, {0: "r0", 1: "r1"}, theta=0.1)
    assert result.seed_size == 2
    assert result.seed_provenance == SEED_INDEPENDENT
    assert result.seed_fraction == 2 / 6
    assert result.theta == 0.1
    assert result.overlap == {"vertices": 6, "left_internal_edges": 5,
                              "recurring_edges": 5, "edge_overlap": 1.0}
    assert result.attack["declared"] > 0
    assert result.attack["precision"] == 1.0
    assert result.seed_only_control["declared"] == 0


def test_declarations_are_split_by_whether_an_image_exists_at_all():
    left = graph(range(5), [(0, 1), (1, 2), (0, 3)])
    right = graph([f"r{i}" for i in range(5)],
                  [("r0", "r1"), ("r1", "r2"), ("r0", "r3")])
    # Vertices 3 and 4 have no image at all: the right view is a different observation, not a
    # relabelling of the left one. Declaring `r3` for vertex 3 is a failure the algorithm has
    # no abstention for, and lumping it in with a wrong image hides which one happened.
    result = run_bitcoin_views(left, right, {0: "r0", 1: "r1", 2: "r2"},
                               {0: "r0", 2: "r2"}, theta=0.1)
    assert result.attack["declared"] == 2
    assert result.attack["declared_with_an_image"] == 1
    assert result.attack["precision"] == 0.5
    assert result.attack["precision_where_an_image_exists"] == 1.0


def test_seed_may_not_be_selected_from_withheld_truth_incorrectly():
    left = graph([0], [])
    right = graph(["r0"], [])
    try:
        run_bitcoin_views(left, right, {0: "r0"}, {0: "wrong"})
    except ValueError as error:
        assert "conflicts" in str(error)
    else:
        raise AssertionError("truth-conflicting seed accepted")


def test_separability_credits_the_attack_only_over_the_shuffled_control():
    left, right, truth = path_views(9)
    result = run_bitcoin_views(left, right, truth, {0: "r0", 8: "r8"})
    # Six of the seven held-out vertices: the last one is the only unclaimed candidate left,
    # and a population of one has no eccentricity, so the algorithm declines it.
    assert result.attack["correct"] == 6
    assert result.shuffled_seed_control["correct"] == 0
    assert result.shuffled_seed_control["fixed_points"] == 0
    assert result.separability["attack_only"] == 6
    assert result.separability["shuffled_only"] == 0
    assert result.separability["p"] < 0.05
    assert result.separability["beats_shuffled"] == "a"


def test_a_real_advantage_too_small_to_separate_is_not_reported_as_a_verdict():
    left, right, truth = path_views(6)
    result = run_bitcoin_views(left, right, truth, {0: "r0", 5: "r5"})
    assert (result.separability["attack_only"], result.separability["shuffled_only"]) == (3, 0)
    # Three discordant wins cannot clear a two-sided sign test at 0.05: measured, not separable.
    assert result.separability["p"] == 0.25
    assert result.separability["beats_shuffled"] is None


def test_a_symmetric_neighbourhood_leaves_the_shuffled_control_mostly_intact():
    """The control falsifies a seed-position artifact, not the algorithm. Where two seeds feed
    the same vertex, swapping them changes no vote there, so the control keeps most of the
    attack's output and the paired advantage is one vertex — no verdict either way."""
    left, right, truth = chain_views()
    result = run_bitcoin_views(left, right, truth, {0: "r0", 1: "r1"}, theta=0.1)
    assert result.attack["correct"] == 3
    assert result.shuffled_seed_control["correct"] == 2
    assert result.separability["attack_only"] == 1
    assert result.separability["beats_shuffled"] is None


def test_isolated_views_report_a_negative_result_rather_than_no_result():
    left = graph(range(4), [])
    right = graph([f"r{i}" for i in range(4)], [])
    truth = {i: f"r{i}" for i in range(4)}
    result = run_bitcoin_views(left, right, truth, {0: "r0", 1: "r1"})
    assert result.attack["declared"] == 0
    assert result.attack["precision"] is None
    assert result.attack["coverage"] == 0.0
    assert result.separability == {"attack_only": 0, "shuffled_only": 0,
                                  "min_correct_gain": 1, "p": 1.0,
                                  "beats_shuffled": None}


def test_sampled_seeds_come_from_the_correspondence_and_are_reproducible():
    truth = {i: f"r{i}" for i in range(20)}
    first = sampled_seeds(truth, 0.25, random.Random(3))
    assert first == sampled_seeds(truth, 0.25, random.Random(3))
    assert len(first) == 5
    assert all(truth[u] == v for u, v in first.items())
    # Never fewer than two: one seed cannot establish an eccentricity at all.
    assert len(sampled_seeds(truth, 0.01, random.Random(3))) == 2


def test_sampled_seeds_are_drawn_uniformly_and_not_in_key_order():
    """Nothing but the signature stops a degree- or order-biased draw, and a biased one would
    seed the vertices propagation finds easiest and report the spread as the attack's reach."""
    truth = {i: f"r{i}" for i in range(10)}
    counts = Counter()
    for seed in range(400):
        counts.update(sampled_seeds(truth, 0.2, random.Random(seed)).keys())
    assert set(counts) == set(truth)
    # 800 draws over 10 keys: 80 expected each, measured 70-88. An order-biased draw would
    # put 400 on the first two keys and nothing on the rest.
    assert 60 <= min(counts.values()) and max(counts.values()) <= 100


def test_manifest_invariants_are_recomputed_and_match_results_ns_bitcoin():
    """`check_manifest` compares invariants only when a caller recomputes and supplies them,
    so this is that caller. It recomputes the two kinds that are cheap: the run configuration,
    from the driver's own defaults (the failure this catches is a changed `--min-degree` or
    `--blocks`, which leaves the epoch bytes and so the digest untouched), and the window
    transaction counts, straight off the compressed epochs. The contracted populations are
    identity-only by design: rebuilding two 100k-vertex views takes minutes, not seconds."""
    args = build_parser().parse_args([])
    if not glob.glob(os.path.join(ROOT, "data", "epochs_2016_weekly", "*.ndjson.gz")):
        pytest.skip("data/epochs_2016_weekly not present; manifest invariants not recomputed")

    invariants = dict(run_configuration(args))
    invariants["left_transactions"] = window_size(
        os.path.join(ROOT, args.left), args.boundary - args.blocks, args.boundary - 1)
    invariants["right_transactions"] = window_size(
        os.path.join(ROOT, args.right), args.boundary, args.boundary + args.blocks - 1)
    status, message = rp.check_manifest("RESULTS-ns-bitcoin.md", invariants, root=ROOT)
    assert status == "partial", message
    assert "not recomputed" in message


def test_eligible_correspondence_drops_pairs_no_view_can_be_graded_on():
    left, right, truth = chain_views()
    truth = {**truth, 99: "r99", 5: "absent"}
    assert eligible_correspondence(left, right, truth) == {i: f"r{i}" for i in range(5)}


def test_sweep_covers_the_grid_and_stamps_every_row_as_seed_assisted():
    left, right, truth = chain_views()
    rows = sweep_bitcoin_views(left, right, truth, [0.3, 0.5], [0.1, 1.5])
    assert [(row.seed_size, row.theta) for row in rows] == [
        (2, 0.1), (2, 1.5), (3, 0.1), (3, 1.5)]
    assert {row.seed_provenance for row in rows} == {SEED_SAMPLED}
    assert [round(row.seed_fraction, 4) for row in rows] == [0.3333, 0.3333, 0.5, 0.5]


def straddling_windows():
    """One cluster active on both sides of the boundary, plus per-window counterparties."""
    before = [tx(499, ["e1", "e2"], ["x1", "x2"]), tx(499, ["x1"], ["x3"]),
              tx(498, ["x2"], ["x3", "1dice8EMZmqKvrGE4Qc9bUFf9PX3xaYDp"])]
    # `e3` is co-spent with `e2` only after the boundary, which is what makes the cluster
    # straddle it: a cluster all of whose addresses were already seen before the boundary
    # is wholly inside view A and there is nothing to rejoin.
    after = [tx(500, ["e2", "e3"], ["y1", "y2"]), tx(500, ["y1"], ["y3"]),
             tx(501, ["y2"], ["y3", "3BMEXvanityaddress"])]
    return before, after


def test_view_construction_gives_a_straddling_cluster_one_pseudonym_per_view():
    before, after = straddling_windows()
    left, right, correspondence, lookups, addresses, split = build_views(
        before, after, min_degree=1, split_frac=1.0, rng=random.Random(0))
    assert split == 1 and len(correspondence) == 1
    (u, v), = correspondence.items()
    assert u.endswith("#a") and v.endswith("#b")
    assert u[:-2] == v[:-2]
    # The trivial escape: no pseudonym string may be shared by the two views.
    assert not set(left.vertices) & set(right.vertices)
    assert addresses >= len({"e1", "e2", "e3", "x1", "x2", "x3", "y1", "y2", "y3"})
    assert graph_overlap(left, right, correspondence)["vertices"] == 1


def test_independent_entity_labels_name_entities_from_the_chain_alone():
    before, after = straddling_windows()
    _, _, _, lookups, _, _ = build_views(before, after, min_degree=1, split_frac=1.0,
                                         rng=random.Random(0))
    left_labels = independent_entity_labels(before, lookups[0])
    right_labels = independent_entity_labels(after, lookups[1])
    assert {entity for entity, _ in left_labels} == {"satoshidice"}
    assert {entity for entity, _ in right_labels} == {"bitmex"}
    # No entity is unambiguous on both sides, so no seed is manufactured.
    assert unique_entity_seeds(left_labels, right_labels) == {}

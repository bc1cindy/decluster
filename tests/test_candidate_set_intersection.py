"""The candidate-set intersection baseline, and the three answers it is allowed to give.

Narrowing to one, narrowing and stopping short, and refusing. The third is the one worth testing
hardest: an empty intersection means the observations contradict each other, and a baseline that
reported it as a maximal narrowing would answer loudest exactly where its premise broke.
"""
import os

import pytest

from decluster import reproducibility as rp
from decluster.baselines import candidate_set_intersection as csi
from decluster.baselines import goldfeder_cluster_intersection, intersect_candidate_sets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = "RESULTS-candidate-set-intersection.md"


def test_successive_observations_narrow_a_longitudinal_set_to_one():
    """The attack's whole shape: no single observation names the origin, and together they do."""
    result = intersect_candidate_sets(
        [{"a", "b", "c", "d"}, {"b", "c", "d"}, {"c", "d", "e"}, {"a", "c"}]
    )
    assert result.surviving == frozenset({"c"})
    assert result.identified == "c"
    assert result.inconsistent_at is None
    assert result.narrowing_bits == pytest.approx(2.0)          # 4 -> 1, relative to the first set
    assert [step.after for step in result.steps] == [4, 3, 2, 1]


def test_a_known_universe_credits_the_first_observation_with_its_own_narrowing():
    """A first set of 8 out of 64 has already said 3 bits. Without the universe there is nothing
    to measure it against, and the run says so by carrying no bits for that step."""
    observations = [set(range(8)), {0, 1, 2, 3}]
    known = intersect_candidate_sets(observations, universe_size=64)
    unknown = intersect_candidate_sets(observations)
    assert known.narrowing_bits == pytest.approx(4.0)
    assert unknown.narrowing_bits == pytest.approx(1.0)
    assert known.steps[0].narrowing_bits == pytest.approx(3.0)
    assert unknown.steps[0].narrowing_bits == pytest.approx(0.0)
    assert known.surviving == unknown.surviving


def test_observations_that_do_not_converge_leave_the_set_wide():
    """Repeating what is already known narrows nothing. The result is a set, not a name."""
    result = intersect_candidate_sets([set(range(8))] * 4, universe_size=64)
    assert len(result.surviving) == 8
    assert result.identified is None, "eight survivors identify nobody"
    assert result.narrowing_bits == pytest.approx(3.0), \
        "all of it from the universe, none from repetition"
    assert [step.narrowing_bits for step in result.steps[1:]] == [0.0, 0.0, 0.0]


def test_a_partial_narrowing_is_reported_as_a_set_and_not_rounded_to_a_name():
    result = intersect_candidate_sets([{"a", "b", "c", "d"}, {"a", "b", "c"}, {"a", "b"}])
    assert result.surviving == frozenset({"a", "b"})
    assert result.identified is None
    assert result.narrowing_bits == pytest.approx(1.0)


def test_inconsistent_observations_are_refused_rather_than_guessed():
    """Disjoint observations contradict each other: either a candidate set is wrong or the coins
    were not co-held. The baseline has no answer and must not manufacture one."""
    result = intersect_candidate_sets([{"a", "b"}, {"c", "d"}], universe_size=64)
    assert result.surviving == frozenset()
    assert result.identified is None
    assert result.inconsistent_at == 1
    assert result.narrowing_bits is None, "an empty intersection is a refusal, not infinite bits"
    assert result.steps[-1].narrowing_bits is None


def test_an_inconsistent_run_stops_rather_than_absorbing_later_observations():
    """Nothing after the contradiction can narrow an empty set, and continuing would let the run
    look like it kept working."""
    result = intersect_candidate_sets([{"a"}, {"b"}, {"a"}, {"a"}])
    assert result.inconsistent_at == 1
    assert len(result.steps) == 2
    assert result.identified is None


def test_an_observation_with_no_candidates_is_a_refusal_not_an_identification():
    result = intersect_candidate_sets([set(), {"a"}])
    assert result.surviving == frozenset() and result.inconsistent_at == 0
    assert result.identified is None and result.narrowing_bits is None


def test_no_observations_is_not_a_refusal():
    """Never asked and asked-and-contradicted are different states."""
    result = intersect_candidate_sets([])
    assert result.surviving == frozenset()
    assert result.steps == ()
    assert result.inconsistent_at is None
    assert result.identified is None


def test_order_does_not_change_what_survives():
    observations = [{"a", "b", "c"}, {"b", "c", "d"}, {"c", "d", "e"}]
    forward = intersect_candidate_sets(observations)
    backward = intersect_candidate_sets(list(reversed(observations)))
    assert forward.surviving == backward.surviving == frozenset({"c"})


def test_the_baseline_takes_candidate_sets_and_computes_none_of_its_own():
    """Independence from this repository's ancestry walk is the separation the module claims;
    a hidden import of it would make the baseline a second opinion on the same walk."""
    source = open(os.path.join(ROOT, "decluster", "baselines",
                               "candidate_set_intersection.py")).read()
    imports = [line.strip() for line in source.splitlines()
               if line.strip().startswith(("import ", "from "))]
    assert imports
    for line in imports:
        assert not line.startswith("from ."), line
        assert "decluster" not in line, line


def test_the_module_scopes_what_is_and_is_not_reproduced():
    """The honesty constraint is part of the deliverable, so it is checked like any other."""
    doc = " ".join(csi.__doc__.split())
    assert "Algorithm 2 is implemented" in doc
    assert "empirical rates are NOT reproduced" in doc
    assert "no shrink law" in doc and "not Goldfeder's" in doc


def test_goldfeder_algorithm_two_uses_only_join_paths_and_identifies_unique_cluster():
    parents = {
        "late-a": ("mid-a", "decoy-a"),
        "mid-a": ("alice-a", "bob-a"),
        "late-b": ("mid-b", "decoy-b"),
        "mid-b": ("alice-b", "carol-b"),
        # These are deliberately absent: non-join ancestors stop traversal.
    }
    clusters = {
        "late-a": "spent-a", "mid-a": "mixed-a", "decoy-a": "dave",
        "alice-a": "alice", "bob-a": "bob",
        "late-b": "spent-b", "mid-b": "mixed-b", "decoy-b": "erin",
        "alice-b": "alice", "carol-b": "carol",
    }

    result = goldfeder_cluster_intersection(
        ["late-a", "late-b"], 2, lambda coin: parents.get(coin, ()), clusters.get
    )
    assert result.identified == "alice"
    assert result.surviving == frozenset({"alice"})
    assert not result.incorrect_assumptions


def test_goldfeder_algorithm_two_refuses_zero_or_multiple_clusters():
    clusters = {"a": "alice", "b": "bob"}
    none = goldfeder_cluster_intersection(
        ["a", "b"], 0, lambda _coin: (), clusters.get
    )
    many = goldfeder_cluster_intersection(
        ["a"], 0, lambda _coin: (), lambda _coin: "alice"
    )
    assert none.surviving == frozenset() and none.incorrect_assumptions
    # A one-coin/one-cluster observation is mechanically unique; test the true
    # multiple-survivor path with one join layer.
    many = goldfeder_cluster_intersection(
        ["a"], 1, lambda _coin: ("b",), clusters.get
    )
    assert many.surviving == frozenset({"alice", "bob"})
    assert many.identified is None and many.incorrect_assumptions


def test_scenarios_are_deterministic():
    assert csi.scenarios() == csi.scenarios()


def test_manifest_invariants_are_recomputed_and_match_results_candidate_set_intersection():
    """`check_manifest` only compares invariants a caller recomputes and passes in, so this is
    that caller. The source is this repository's own module text, so an `absent` status means the
    file the document was measured from is gone -- reported, not passed over."""
    measured = csi.manifest_invariants()
    status, message = rp.check_manifest(DOC, measured, root=ROOT)
    if status == "absent":
        pytest.skip(message)
    assert status == "ok", message


def test_every_number_in_the_manifest_is_stated_in_the_document():
    recorded = rp.read_manifest(DOC, root=ROOT)
    assert recorded is not None, f"{DOC} has no manifest"
    text = open(os.path.join(ROOT, "results", DOC)).read()
    for key, value in recorded["invariants"].items():
        if value is None:
            continue
        assert str(value) in text, f"{key}={value} is not stated in {DOC}"


def test_the_document_is_indexed_in_the_reproducibility_policy():
    policy = open(os.path.join(ROOT, "results", "REPRODUCIBILITY.md")).read()
    assert DOC[:-3] in policy

"""Whether the matcher beats degree alone, and whether it knows which answers are good.

The two documents this replaces were measured on a slice that no longer exists. What is asserted
here is what they were read for, rather than the numbers they happened to land on: that the
comparison is made against the exact degree-class expectation and not only against chance, that a
shuffled-seed arm runs beside every seeded one, and that precision is reported against the
eccentricity each match won by so the framework's own criterion — high-confidence links — can be
read off it.

The seedable band is asserted too. Propagation refuses to route through a matched neighbour above
the hub cap, so seeding by raw degree hands the matcher a budget of vertices it discards; that
mistake is cheap to make and invisible in the output, which is why the band is a property here and
not a comment.
"""

import json
from pathlib import Path

import pytest

from decluster.experiments import match_controls as mc

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "results" / "artifacts" / "match-controls-v1.json"
EPOCHS = tuple(ROOT / path for path in mc.DEFAULT_EPOCHS)


@pytest.fixture(scope="module")
def artifact():
    if not ARTIFACT.is_file():
        pytest.skip("the canonical match-controls artifact is not committed")
    return json.loads(ARTIFACT.read_text())


def _widest(artifact):
    return artifact["confidence"][max(artifact["confidence"], key=float)]


def test_seeds_come_from_the_band_the_matcher_can_spend_them_in(artifact):
    population = artifact["population"]
    assert 0 < population["seedable"] < population["matchable_in_both_views"], (
        "seeds are no longer drawn from a band; a hub handed to the matcher is evidence it refuses "
        "to route through")
    assert mc.SEEDABLE[1] == 100, "the band's ceiling has to track the matcher's hub cap"


def test_every_seeded_arm_has_a_shuffled_arm_beside_it(artifact):
    arms = artifact["matching"]
    seeded = {row["seed_share"] for row in arms if row["arm"] == "seeded"}
    shuffled = {row["seed_share"] for row in arms if row["arm"] == "shuffled"}
    assert seeded and seeded == shuffled


def test_the_shuffle_control_does_not_keep_up_with_the_seeds(artifact):
    """A correspondence destroyed and still recovered would mean the seeds carried nothing."""
    by_key = {(row["seed_share"], row["arm"]): row for row in artifact["matching"]}
    for share in {row["seed_share"] for row in artifact["matching"]}:
        seeded, shuffled = by_key[(share, "seeded")], by_key[(share, "shuffled")]
        assert shuffled["correct"] <= seeded["correct"]


def test_the_bands_are_scored_against_degree_and_not_only_against_chance(artifact):
    for row in _widest(artifact):
        if row["matched"]:
            assert row["degree_class_expectation"] is not None, (
                "a band without its degree-class column is a precision nobody can read")


def test_raising_the_confidence_floor_never_admits_more_matches(artifact):
    bands = _widest(artifact)
    counts = [row["matched"] for row in bands]
    assert counts == sorted(counts, reverse=True)
    assert [row["eccentricity_at_least"] for row in bands] == sorted(
        row["eccentricity_at_least"] for row in bands)


def test_the_margin_over_degree_collapses_where_the_matcher_is_most_confident(artifact):
    """The reading the replaced document got backwards, asserted so it cannot drift back.

    It reported the margin over a degree-only guess *growing* into the high-confidence band. On
    committed data it falls: precision rises with the matcher's confidence, but the degree baseline
    rises faster, because the matches it is surest of are the ones whose partner has a rare degree.
    """
    for bands in artifact["confidence"].values():
        overall, narrowest = bands[0], bands[-1]
        assert overall["precision"] > overall["degree_class_expectation"], (
            "the matcher no longer beats degree at all, which is a different result again")
        assert narrowest["precision"] > overall["precision"], (
            "precision is no longer monotone in the matcher's own confidence")
        wide = overall["precision"] - overall["degree_class_expectation"]
        tight = narrowest["precision"] - narrowest["degree_class_expectation"]
        assert tight < wide / 2, (
            "the margin no longer collapses into the high-confidence band; the document's central "
            "reading has changed and its prose has to change with it")


def test_the_bands_are_gate_decisions_and_not_lone_candidates(artifact):
    """An uncontested match skips the gate, so a band made of them would say nothing about it."""
    for bands in artifact["confidence"].values():
        assert bands[-1]["uncontested"] < 0.1 * bands[-1]["matched"]


def test_the_seeds_carry_information_the_shuffle_destroys(artifact):
    by_key = {(row["seed_share"], row["arm"]): row for row in artifact["matching"]}
    for share in {row["seed_share"] for row in artifact["matching"]}:
        seeded, shuffled = by_key[(share, "seeded")], by_key[(share, "shuffled")]
        assert shuffled["guesses"] < 0.05 * seeded["guesses"]


@pytest.mark.reproduction
def test_the_committed_artifact_is_what_a_fresh_run_produces(artifact):
    if not all(path.is_file() for path in EPOCHS):
        pytest.skip("the committed weekly epoch graphs are not present")
    mc.verify_artifact(artifact, tuple(str(path) for path in EPOCHS))

"""The rejoin measurement, taken again on data that exists.

The numbers this run carries were first measured on a 1.1 GB slice that is gone, so they could
neither be checked nor taken again. The committed weekly graph holds the same object, and the run
lands on the same population: 17,431 clusters straddling the boundary, 15,688 of them offered to the
matcher once a tenth are seeded. The published figure was one correct rejoin out of that 15,688.
"""

import json
import random
from pathlib import Path

import pytest

from decluster.experiments import graph_rejoin_2016 as gr

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "results" / "artifacts" / "graph-rejoin-2016-v1.json"


@pytest.fixture(scope="module")
def artifact():
    if not ARTIFACT.is_file():
        pytest.skip("the canonical graph-rejoin artifact is not committed")
    return json.loads(ARTIFACT.read_text())


def test_shuffled_control_starts_from_the_ranked_seed_order():
    ordered = ["v9", "v2", "v7", "v1"]
    truth = {vertex: f"image-{vertex}" for vertex in ordered}
    seeds, supplied, shuffled = gr._seed_arms(ordered, truth, 3, random.Random(0))

    assert seeds == set(ordered[:3])
    assert list(supplied) == ordered[:3]
    assert set(shuffled) == set(ordered[:3])
    assert sorted(shuffled.values()) == sorted(supplied.values())


def test_every_seeded_arm_runs_beside_a_shuffled_one(artifact):
    """A seeded arm without its control cannot say whether the graph answered or the matcher did."""
    seen = {(row["seed_share"], row["matcher"], row["arm"]) for row in artifact["matching"]}
    for share, matcher, _ in list(seen):
        assert (share, matcher, "seeded") in seen and (share, matcher, "shuffled") in seen


def test_the_shuffled_controls_recover_nothing(artifact):
    """The claim the seeded arms rest on: what little they find is not the matcher answering itself."""
    shuffled = [row for row in artifact["matching"] if row["arm"] == "shuffled"]
    assert shuffled, "no control arm ran"
    assert all(row["correct"] == 0 for row in shuffled)


def test_the_cascade_does_not_ignite(artifact):
    """Stated as a bound, so a future run that does ignite fails here rather than passing quietly."""
    seeded = [row for row in artifact["matching"] if row["arm"] == "seeded"]
    correct = sum(row["correct"] for row in seeded)
    offered = artifact["population"]["pairs_to_rejoin"]
    assert correct <= 2, f"{correct} rejoins of {offered}: this is no longer a null result"


def test_the_population_is_the_one_the_published_measurement_names(artifact):
    population = artifact["population"]
    assert population["pairs_to_rejoin"] == 17431
    assert abs(population["mean_internal_degree"] - 2.866) < 5e-4
    widest = max(row["seeds"] for row in artifact["matching"])
    assert population["pairs_to_rejoin"] - widest == 15688


@pytest.mark.reproduction
def test_the_committed_artifact_is_what_a_fresh_run_produces(artifact):
    if not (ROOT / gr.DEFAULT_EPOCHS[0]).is_file():
        pytest.skip("the committed epoch graphs are not present")
    gr.verify_artifact(artifact)

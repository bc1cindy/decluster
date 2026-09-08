"""The cut the framework states robust connectivity over, measured for the first time.

`path_count` accumulates route mass and says in its own docstring that this is a different number:
many routes may run through one coin, so a large count is consistent with a cut of one. On the
committed cache the two disagree for three coins in every five, which is what this run reports.

The boundary counts are part of the result rather than diagnostics beside it. Almost every origin
the walk reaches is the edge of the slice rather than a coinbase, so every cut here is a lower bound
and the document has to say by how much — a reader given the fragility without the sample limit
would take a floor for a ceiling.
"""

import json
from pathlib import Path

import pytest

from decluster.experiments import route_capacity as rc

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "results" / "artifacts" / "route-capacity-v1.json"
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.fixture(scope="module")
def artifact():
    if not ARTIFACT.is_file():
        pytest.skip("the canonical route-capacity artifact is not committed")
    return json.loads(ARTIFACT.read_text())


def test_every_measured_coin_lands_in_the_distribution(artifact):
    assert sum(artifact["capacity"].values()) == artifact["population"]["measured"]
    assert sum(artifact["origin_excess"].values()) == artifact["population"]["measured"]


def test_no_coin_is_reported_with_more_routes_than_it_has_origins(artifact):
    """`origins - k` is a count of routes an origin set promises and the graph does not deliver."""
    assert min(int(gap) for gap in artifact["origin_excess"]) >= 0


def test_the_origin_set_overstates_redundancy_for_most_coins(artifact):
    """The finding the module exists for, asserted rather than left in a table."""
    measured = artifact["population"]["measured"]
    overstated = artifact["readings"]["origin_set_overstates"]
    assert overstated / measured > 0.5, (
        f"{overstated}/{measured}: counting origins no longer overstates the cut, which would "
        "make this measurement redundant with path_count")


def test_a_cut_of_one_is_reported_and_bounded(artifact):
    """Stated as a band: a run that finds none, or finds it everywhere, has changed the object."""
    measured = artifact["population"]["measured"]
    fragile = artifact["readings"]["cut_of_one"]
    assert 0 < fragile < measured * 0.5, f"{fragile}/{measured} coins fall to a single-coin cut"


def test_the_boundary_the_walk_stopped_at_is_recorded(artifact):
    """Without this the fragility reads as a property of the chain rather than of the sample."""
    causes = artifact["boundary_causes"]
    assert set(causes) >= {"fetch_missing", "depth_capped", "coinbase"}
    assert causes["fetch_missing"] > causes["depth_capped"], (
        "the slice now bounds the walk less than the depth limit does; the document's reading of "
        "these cuts as sample-bounded lower bounds needs rewriting")


def test_the_document_states_the_sample_limit_beside_the_fragility(artifact):
    """The number and its caveat travel together or the number is misread."""
    rendered = rc.render_markdown(artifact)
    assert str(artifact["readings"]["cut_of_one"]) in rendered
    assert str(artifact["boundary_causes"]["fetch_missing"]) in rendered
    assert "lower bound" in rendered


@pytest.mark.reproduction
def test_the_committed_artifact_is_what_a_fresh_run_produces(artifact):
    if not SNAPSHOT.is_file():
        pytest.skip("the block-cache snapshot is not committed")
    rc.verify_artifact(artifact, str(SNAPSHOT))

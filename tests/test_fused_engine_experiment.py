"""The fusion is the object the argument rests on, and it was the one nothing published executed.

Every channel had a canonical run; `cluster_refined`, which fuses them, had none. It ran in unit
tests on stubs and in scripts over data this repository does not ship, so no committed artifact ever
exercised the engine itself. These pin the run that closes that.
"""

import json
from pathlib import Path

import pytest

from decluster.experiments import fused_engine as fe

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "results" / "artifacts" / "fused-engine-v1.json"
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.fixture(scope="module")
def artifact():
    if not ARTIFACT.is_file():
        pytest.skip("the canonical fused-engine artifact is not committed")
    return json.loads(ARTIFACT.read_text())


def test_the_ladder_switches_on_every_channel_the_engine_fuses(artifact):
    """A ladder that skips a channel would report a fusion the engine never performed."""
    arms = [row["arm"] for row in artifact["ladder"]]
    assert arms[0] == "fingerprint"
    assert arms[-1] == "all five channels"
    for channel in ("amount", "topology", "provenance"):
        assert any(channel in arm for arm in arms), f"{channel} is never switched on"


def test_the_engine_refuses_cospends_the_merge_only_baseline_takes(artifact):
    """The thesis in one assertion: the baseline merges what the engine declines."""
    baseline = artifact["cospend_baseline"]
    assert baseline["refused_cospends"] == 0
    assert all(row["refused_cospends"] > 0 for row in artifact["ladder"])
    assert all(row["groups"] < baseline["groups"] for row in artifact["ladder"]), (
        "the fingerprint link channel should still collapse more than co-spend alone")


def test_topology_and_provenance_move_refusals_in_opposite_directions(artifact):
    """Fusing is only worth doing where the channels disagree; this is where they do."""
    by_arm = {row["arm"]: row for row in artifact["ladder"]}
    fingerprint = by_arm["fingerprint+amount"]["refused_cospends"]
    topology = by_arm["fingerprint+amount+topology"]["refused_cospends"]
    provenance = by_arm["fingerprint+amount+topology+provenance"]["refused_cospends"]
    assert topology < fingerprint, "topology should corroborate merges the fingerprint objected to"
    assert provenance > topology, "provenance-disjointness should cut pairs topology kept"


@pytest.mark.reproduction
def test_the_committed_artifact_is_what_a_fresh_run_produces(artifact):
    if not SNAPSHOT.is_file():
        pytest.skip("the block-cache snapshot is not committed")
    fe.verify_artifact(artifact, str(SNAPSHOT))

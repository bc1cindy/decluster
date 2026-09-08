"""The asymmetry §2 rests on, taken again on data a reader has.

A merged transaction contributes about 1.6 bits of ambiguity and an established cluster carries far
more, so the partition is decidable without the merge. That figure came from a slice that no longer
exists, which left the argument's load-bearing number unverifiable; on the committed cache it lands
in the same place and the comparison it is needed for does not move at all.

The five-rarest floor is checked rather than asserted. Ninety-two per cent of these clusters have at
most five counterparties, so the restriction usually keeps the whole set — a floor that repeats the
number above it tests nothing, and the document has to say so instead of borrowing the rigour.
"""

import json
from pathlib import Path

import pytest

from decluster.experiments import cluster_bits as cb

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "results" / "artifacts" / "cluster-bits-v1.json"
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.fixture(scope="module")
def artifact():
    if not ARTIFACT.is_file():
        pytest.skip("the canonical cluster-bits artifact is not committed")
    return json.loads(ARTIFACT.read_text())


def test_every_cluster_clears_the_merge_it_would_have_to_hide_behind(artifact):
    """The comparison the paper makes, asserted where a future slice can break it."""
    merge = str(artifact["parameters"]["merge_ambiguity_bits"])
    assert artifact["share_at_least"][merge] == 1.0, (
        "a cluster now carries less identifying structure than the merge's ambiguity, which is the "
        "premise of section 2")


def test_the_median_is_an_order_of_magnitude_above_the_merge(artifact):
    merge = artifact["parameters"]["merge_ambiguity_bits"]
    assert artifact["bits"]["median"] > 10 * merge


def test_the_topk_floor_is_reported_with_the_reason_it_says_little(artifact):
    """It equals the median because the clusters are small; claiming independence would be false."""
    population = artifact["population"]
    small = population["clusters_with_at_most_topk_counterparties"] / population["clusters"]
    assert small > 0.5, "most clusters no longer fit inside the top-k, so the floor now means more"
    rendered = cb.render_markdown(artifact)
    assert f"{small:.0%}" in rendered and "says only that the clusters are small" in rendered


def test_the_identifier_excludes_the_edges_that_built_the_cluster(artifact):
    """A co-spend edge cannot be the quasi-identifier of the cluster co-spending defined."""
    assert "co-spend excluded" in artifact["parameters"]["graph"]


@pytest.mark.reproduction
def test_the_committed_artifact_is_what_a_fresh_run_produces(artifact):
    if not SNAPSHOT.is_file():
        pytest.skip("the block-cache snapshot is not committed")
    cb.verify_artifact(artifact, str(SNAPSHOT))

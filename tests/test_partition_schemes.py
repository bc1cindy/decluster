"""The cut comparison the framework asked for, reproducing the published table.

It used to rest on a 977 MB export nobody else held. The run consumes one prefix of it, that prefix
recompresses to 50 MB, and it is now committed — so every figure in `RESULTS-partition-cuts.md` is
checkable rather than asserted.
"""
import json

import pytest

from decluster.experiments import partition_schemes as experiment


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact()


def test_reproduce_then_verify(tmp_path):
    art, markdown = tmp_path / "a.json", tmp_path / "a.md"
    assert experiment.main(["reproduce", "--artifact", str(art), "--markdown", str(markdown)]) == 0
    assert experiment.main(["verify", "--artifact", str(art), "--markdown", str(markdown)]) == 0


def test_the_collapse_cut_tracks_the_temporal_one(artifact):
    rows = {row["scheme"]: row for row in artifact["measurement"]["schemes"]}
    assert abs(rows["collapse"]["straddling_entities"] - rows["epoch"]["straddling_entities"]) <= 40
    assert rows["collapse"]["mean_straddler_degree"] >= rows["epoch"]["mean_straddler_degree"]
    assert rows["collapse"]["boundary_transactions"] < 0.05 * artifact["measurement"]["transactions"]


def test_decore_is_the_scheme_that_destroys_the_signal(artifact):
    rows = {row["scheme"]: row for row in artifact["measurement"]["schemes"]}
    assert rows["decore"]["mean_straddler_degree"] < rows["epoch"]["mean_straddler_degree"] / 2
    assert rows["decore"]["straddling_entities"] < rows["epoch"]["straddling_entities"] / 1.5
    assert rows["decore"]["boundary_transactions"] > 0.3 * artifact["measurement"]["transactions"]


def test_a_seed_share_that_yields_no_guess_reports_no_precision(artifact):
    """Zero guesses is not zero precision; printing the second reads as a measured tie."""
    for row in artifact["measurement"]["schemes"]:
        for seed in row["seeded"]:
            if seed["guesses"] == 0:
                assert seed["precision"] is None
            else:
                assert seed["precision"] is not None


def test_the_published_table_is_reproduced(artifact):
    """The figures RESULTS-partition-cuts.md reports, which had no reproducible source."""
    rows = {row["scheme"]: row for row in artifact["measurement"]["schemes"]}
    assert artifact["measurement"]["transactions"] == 300000
    assert rows["epoch"]["straddling_entities"] == 2562
    assert rows["decore"]["straddling_entities"] == 1294
    assert rows["collapse"]["straddling_entities"] == 2536
    assert rows["collapse"]["edges_among_straddlers"] == 1941


def test_every_scheme_reports_the_view_counts_it_was_asked_for(artifact):
    for scheme, counts in artifact["measurement"]["view_counts"].items():
        for asked, sizes in counts.items():
            assert len(sizes) == int(asked), f"{scheme} at n_views={asked}"


def test_a_tampered_artifact_is_refused(artifact):
    stored = json.loads(json.dumps(artifact))
    stored["measurement"]["schemes"][0]["straddling_entities"] += 1
    with pytest.raises(experiment.VerificationError):
        experiment.verify_artifact(stored)

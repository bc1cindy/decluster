"""The cut comparison the framework asked for, on committed data.

The published version of this comparison rests on a 977 MB export the repository does not ship, so
the one property that matters here is that the run says what it cannot show rather than filling it
in with zeros.
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
    assert abs(rows["collapse"]["straddling_entities"] - rows["epoch"]["straddling_entities"]) <= 5
    assert abs(rows["collapse"]["edges_among_straddlers"] - rows["epoch"]["edges_among_straddlers"]) <= 5


def test_decore_is_the_scheme_that_destroys_the_signal(artifact):
    rows = {row["scheme"]: row for row in artifact["measurement"]["schemes"]}
    assert rows["decore"]["edges_among_straddlers"] < rows["epoch"]["edges_among_straddlers"] / 2


def test_a_matcher_that_makes_no_guess_is_reported_as_such(artifact):
    """Zero guesses is not zero precision, and printing the second would read as a measured tie."""
    measured = artifact["measurement"]
    assert measured["any_scheme_ignited_the_matcher"] is False
    for row in measured["schemes"]:
        assert "matcher_guesses" in row and "precision" not in row


def test_every_scheme_reports_the_view_counts_it_was_asked_for(artifact):
    for scheme, counts in artifact["measurement"]["view_counts"].items():
        for asked, sizes in counts.items():
            assert len(sizes) == int(asked), f"{scheme} at n_views={asked}"


def test_a_tampered_artifact_is_refused(artifact):
    stored = json.loads(json.dumps(artifact))
    stored["measurement"]["schemes"][0]["straddling_entities"] += 1
    with pytest.raises(experiment.VerificationError):
        experiment.verify_artifact(stored)

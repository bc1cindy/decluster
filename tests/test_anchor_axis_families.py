"""The one edge PAPER §4 argues from, and the properties that argument needs."""
import json

import pytest

from decluster.experiments import anchor_axis_families as experiment


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact()


def test_reproduce_then_verify(tmp_path):
    art, markdown = tmp_path / "a.json", tmp_path / "a.md"
    assert experiment.main(["reproduce", "--artifact", str(art), "--markdown", str(markdown)]) == 0
    assert experiment.main(["verify", "--artifact", str(art), "--markdown", str(markdown)]) == 0


def test_the_engine_refuses_and_the_wide_library_links(artifact):
    families = artifact["measurement"]["families"]
    assert families["engine_three_axis"]["verdict"] == "refuse"
    assert families["catalogued"]["verdict"] == "link"
    assert families["catalogued"]["past_link_above"]


def test_dropping_the_redundant_axes_brings_it_back_under_the_threshold(artifact):
    families = artifact["measurement"]["families"]
    assert not families["decorrelated"]["past_link_above"]
    assert artifact["measurement"]["redundancy_bits"] > 0


def test_the_discriminating_axes_still_refuse_and_are_outvoted(artifact):
    measured = artifact["measurement"]
    assert measured["negative_bits_total"] < 0
    assert measured["positive_bits_total"] > -measured["negative_bits_total"]


def test_an_abstaining_axis_carries_no_bits(artifact):
    rows = artifact["measurement"]["per_axis"]
    assert any(row["bits"] is None for row in rows)
    scored = [row for row in rows if row["bits"] is not None]
    assert len(scored) == artifact["measurement"]["catalogued_axes_scored"]


def test_a_fixture_missing_a_txid_is_refused(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"anchor": "x", "transactions": {"cake": {}, "sender": {}}}))
    with pytest.raises(experiment.VerificationError, match="txid"):
        experiment.build_artifact(str(broken))

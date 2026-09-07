import pytest

from decluster.experiments import ns1r_change_readoff as experiment


def test_reproduce_then_verify(tmp_path):
    artifact, markdown = tmp_path / "a.json", tmp_path / "a.md"
    assert experiment.main(["reproduce", "--artifact", str(artifact), "--markdown", str(markdown)]) == 0
    assert experiment.main(["verify", "--artifact", str(artifact), "--markdown", str(markdown)]) == 0


def test_a_tampered_artifact_is_refused(tmp_path):
    artifact = tmp_path / "a.json"
    experiment.main(["reproduce", "--artifact", str(artifact), "--markdown", str(tmp_path / "a.md")])
    stored = experiment.load_artifact(artifact)
    stored["scenarios"][0]["distinct_readings"] += 1
    with pytest.raises(experiment.VerificationError):
        experiment.verify_artifact(stored)


def test_a_reading_is_amounts_not_an_index_matching():
    # The consolidating receiver admits two matchings that differ only in which index each sender's
    # change sits at; the receiver reads one set of amounts, and that is what the leak is.
    rows = {row["identifier"]: row for row in experiment.build_artifact()["scenarios"]}
    consolidating = rows["consolidating-receiver"]
    assert consolidating["matchings"] == 2
    assert consolidating["distinct_readings"] == 1 and consolidating["reading_is_unique"]


def test_the_control_stays_ambiguous():
    rows = {row["identifier"]: row for row in experiment.build_artifact()["scenarios"]}
    control = rows["evenly-spaced-control"]
    assert control["distinct_readings"] > 1
    assert not control["reading_is_unique"] and control["unanimous_links"] == []


def test_propagation_only_ever_narrows_a_sender():
    for row in experiment.build_artifact()["scenarios"]:
        for sender, local in row["local_candidates"].items():
            assert set(row["feasible_candidates"][sender]) <= set(local)

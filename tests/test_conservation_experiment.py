import json

import pytest

from decluster.experiments import conservation_round_three as experiment


def test_artifact_preserves_the_reduced_round_observation():
    artifact = experiment.build_artifact()

    assert artifact["fixture"]["outputs"] == 502
    assert artifact["largest_forced_denomination"] == {
        "value": 774840978,
        "forced": 2,
        "present": 7,
        "forced_value": 1549681956,
        "margin": 360201666,
    }
    assert artifact["interpretation"] == "forced provenance of value under conservation"


def test_fixture_validation_rejects_duplicate_denominations(tmp_path):
    fixture = experiment.load_fixture()
    fixture["outputs"].append(fixture["outputs"][0])
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(experiment.VerificationError, match="must be unique"):
        experiment.load_fixture(path)


def test_verifier_recomputes_the_observation():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["largest_forced_denomination"]["forced"] = 3

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(changed)


def test_cli_reproduces_and_verifies_json_and_markdown(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "--dataset", experiment.DATASET,
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main([
        "--dataset", experiment.DATASET,
        "verify", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0

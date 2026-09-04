import json

import pytest

from decluster.experiments import statistical_disclosure as experiment


def test_artifact_contains_recovery_and_null_control():
    artifact = experiment.build_artifact()

    assert artifact["persistent_correspondent"]["unique_top_correspondent"] == "alice"
    assert artifact["persistent_correspondent"]["top_margin"] == pytest.approx(1.0)
    assert artifact["background_matched_control"]["unique_top_correspondent"] is None
    assert artifact["composition"] is None


def test_verifier_recomputes_the_estimator():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["persistent_correspondent"]["top_margin"] = 0.5

    with pytest.raises(experiment.VerificationError, match="fresh failure-mode"):
        experiment.verify_artifact(changed)


def test_cli_reproduces_and_verifies_json_and_markdown(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"

    assert experiment.main(
        ["reproduce", "--artifact", str(artifact), "--markdown", str(markdown)]
    ) == 0
    assert experiment.main(
        ["verify", "--artifact", str(artifact), "--markdown", str(markdown)]
    ) == 0

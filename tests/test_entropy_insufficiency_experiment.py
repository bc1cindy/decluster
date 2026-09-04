import json

import pytest

from decluster.experiments import entropy_insufficiency as experiment


def test_artifact_preserves_equal_entropy_and_different_residual_ambiguity():
    artifact = experiment.build_artifact()

    assert artifact["equal_initial_entropy"] is True
    assert artifact["brittle_overlap"]["entropy_bits"] == pytest.approx(2.0)
    assert artifact["overlapping_crowd"]["entropy_bits"] == pytest.approx(2.0)
    assert artifact["brittle_overlap"]["surviving_candidates"] == 1
    assert artifact["overlapping_crowd"]["surviving_candidates"] == 2
    assert artifact["composition"] is None


def test_verifier_recomputes_the_counterexample():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["overlapping_crowd"]["surviving_candidates"] = 1

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

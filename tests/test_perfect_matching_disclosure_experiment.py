import json

import pytest

from decluster.experiments import perfect_matching_disclosure as experiment


def test_artifact_distinguishes_joint_assignment_from_tied_control():
    artifact = experiment.build_artifact()
    joint = artifact["joint_assignment"]
    control = artifact["uniform_profile_control"]

    assert joint["naive_is_bijective"] is False
    assert joint["optimal_assignments"] == [[0, 1, 2]]
    assert joint["joint_likelihood"] == pytest.approx(0.192)
    assert joint["unique_assignment_recovered"] is True
    assert control["optimal_assignment_count"] == 6
    assert control["unique_assignment_recovered"] is False


def test_verifier_recomputes_the_joint_objective():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["joint_assignment"]["optimal_assignment_count"] = 2

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

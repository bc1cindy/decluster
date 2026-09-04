import json

import pytest

from decluster.experiments import change_consolidation as experiment


def test_artifact_preserves_retroactive_linkage_without_composition():
    artifact = experiment.build_artifact()
    assert artifact["scenario"]["payments"] == ["payment-1", "payment-2"]
    assert artifact["result"] == {
        "candidates_before": 2,
        "candidates_after": ["alice"],
        "outcome": "candidate_narrowing",
        "composition": None,
    }


def test_verifier_recomputes_the_result():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["result"]["candidates_after"] = ["bob"]
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

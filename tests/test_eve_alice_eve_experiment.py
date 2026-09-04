import json

import pytest

from decluster.experiments import eve_alice_eve as experiment


def test_artifact_contrasts_isolated_and_consolidated_returns():
    artifact = experiment.build_artifact()

    assert artifact["isolated_return"] == {
        "observations": 1,
        "outcome": "inconclusive",
        "candidates_after": [],
        "composition": None,
    }
    assert artifact["consolidated_return"] == {
        "observations": 2,
        "outcome": "candidate_narrowing",
        "candidates_after": ["alice"],
        "composition": None,
    }


def test_verifier_recomputes_both_scenarios():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["consolidated_return"]["candidates_after"] = ["bob"]

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

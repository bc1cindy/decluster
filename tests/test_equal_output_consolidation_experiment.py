import json

import pytest

from decluster.experiments import equal_output_consolidation as experiment
from decluster.result_artifacts import canonical_json_bytes


def test_artifact_preserves_conditional_narrowing_without_composition():
    artifact = experiment.build_artifact()

    assert artifact["scenario"]["candidate_sets"] == [
        ["alice", "bob", "carol"],
        ["alice", "dave", "erin"],
    ]
    assert artifact["result"] == {
        "candidates_before": 3,
        "candidates_after": ["alice"],
        "outcome": "candidate_narrowing",
        "composition": None,
    }
    assert "conditional narrowing" in artifact["limitations"][1]
    assert canonical_json_bytes(artifact) == canonical_json_bytes(experiment.build_artifact())


def test_verifier_recomputes_instead_of_trusting_the_stored_result():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["result"]["candidates_after"] = ["bob"]

    with pytest.raises(experiment.VerificationError, match="fresh failure-mode"):
        experiment.verify_artifact(changed)


def test_cli_reproduces_and_verifies_artifact_and_markdown(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"

    assert experiment.main([
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown)
    ]) == 0
    assert experiment.main([
        "verify", "--artifact", str(artifact), "--markdown", str(markdown)
    ]) == 0
    markdown.write_text(markdown.read_text() + "changed\n")
    with pytest.raises(experiment.VerificationError, match="Markdown differs"):
        experiment.main([
            "verify", "--artifact", str(artifact), "--markdown", str(markdown)
        ])

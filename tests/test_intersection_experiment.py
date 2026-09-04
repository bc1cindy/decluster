import json

import pytest

from decluster.experiments import intersection_fixture as experiment
from decluster.result_artifacts import canonical_json_bytes


def test_artifact_is_deterministic_and_keeps_the_claim_conditional():
    artifact = experiment.build_artifact()

    assert canonical_json_bytes(artifact) == canonical_json_bytes(experiment.build_artifact())
    assert artifact["summary"] == {
        "blind": False,
        "branches": 2,
        "candidates_before": 2,
        "candidates_after": 1,
        "collapsed": 1,
        "scored": False,
    }
    assert any(
        "does not run the clustering verdict" in limitation
        for limitation in artifact["limitations"]
    )


def test_verifier_recomputes_instead_of_trusting_stored_numbers():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["summary"]["candidates_after"] = 0

    with pytest.raises(experiment.VerificationError, match="fresh fixture"):
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

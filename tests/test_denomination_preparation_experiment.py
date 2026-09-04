import json

import pytest

from decluster.experiments import denomination_preparation as experiment


def test_artifact_separates_the_paired_synthetic_populations():
    artifact = experiment.build_artifact()

    assert artifact["preparations"]["fingerprint_matches"] == 3
    assert artifact["arity_matched_controls"]["fingerprint_matches"] == 0
    assert artifact["composition"] is None


def test_verifier_recomputes_the_fingerprint():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["arity_matched_controls"]["fingerprint_matches"] = 1

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

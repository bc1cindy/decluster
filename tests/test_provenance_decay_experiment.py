import json

import pytest

from decluster.experiments import provenance_decay as experiment


def test_artifact_separates_additive_decay_from_graph_fracture():
    artifact = experiment.build_artifact()

    assert artifact["bridge_removal"] == {
        "candidates_before": 3,
        "candidates_after": 2,
        "structural_outcome": "graph_fracture",
        "components_before": 1,
        "components_after": 2,
    }
    assert artifact["peripheral_removal"] == {
        "candidates_before": 3,
        "candidates_after": 2,
        "structural_outcome": "inconclusive",
    }
    assert artifact["composition"] is None


def test_verifier_recomputes_the_structural_measurement():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["bridge_removal"]["components_after"] = 3

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

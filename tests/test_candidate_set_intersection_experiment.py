import json

import pytest

from decluster.experiments import candidate_set_intersection as experiment
from decluster.result_artifacts import canonical_json_bytes


def test_artifact_is_deterministic_and_preserves_refusal():
    artifact = experiment.build_artifact()

    assert canonical_json_bytes(artifact) == canonical_json_bytes(experiment.build_artifact())
    scenarios = {scenario["name"]: scenario for scenario in artifact["scenarios"]}
    assert scenarios["converging"]["identified"] == 0
    assert scenarios["stalled"]["identified"] is None
    assert scenarios["contradictory"]["surviving"] == []
    assert scenarios["contradictory"]["narrowing_bits"] is None
    assert scenarios["contradictory"]["inconsistent_at"] == 1


def test_verifier_recomputes_instead_of_trusting_summary():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["summary"]["identifications"] = 2

    with pytest.raises(experiment.VerificationError, match="fresh fixture"):
        experiment.verify_artifact(changed)


def test_cli_reproduces_and_verifies_both_outputs(tmp_path):
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

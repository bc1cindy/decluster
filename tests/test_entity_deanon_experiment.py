import json

import pytest

from decluster.experiments import entity_deanon as experiment


def test_artifact_preserves_positive_and_null_controls():
    artifact = experiment.build_artifact()

    assert artifact["satoshidice"]["payment_auc"] >= 0.65
    assert 7.0 <= artifact["satoshidice"]["positive_mean_shared_neighbours"] <= 9.0
    assert 0.45 <= artifact["bitmex"]["payment_auc"] <= 0.55
    assert artifact["bitmex"]["positive_mean_shared_neighbours"] < 1.0


def test_verifier_recomputes_both_snapshots():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["bitmex"]["payment_auc"] = 0.75

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(changed)


def test_cli_reproduces_and_verifies_json_and_markdown(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main([
        "verify", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0

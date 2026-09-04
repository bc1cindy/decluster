import pytest

from decluster.experiments import ancestry_contract as experiment


def test_contract_separates_provenance_states_and_truncation_causes():
    artifact = experiment.build_artifact()
    assert artifact["complete"]["is_complete"] is True
    assert artifact["complete"]["distribution"] == {"left:0": 0.5, "right:0": 0.5}
    assert artifact["complete"]["expected_paper_steps"] == pytest.approx(4.0)
    assert artifact["bounded"]["truncation"]["node_capped"] == 2
    assert artifact["bounded"]["truncation"]["oracle_refused"] == 0
    assert artifact["oracle_refusal"]["truncation"]["oracle_refused"] == 1
    assert artifact["oracle_refusal"]["truncation"]["node_capped"] == 0
    assert artifact["overlap"] == {"self": 1.0, "disjoint": 0.0}


def test_reproduce_then_verify_round_trip(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main([
        "verify", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0


def test_verify_rejects_modified_artifact():
    artifact = experiment.build_artifact()
    artifact["overlap"]["disjoint"] = 0.5
    with pytest.raises(experiment.VerificationError, match="differs"):
        experiment.verify_artifact(artifact)

import json

import pytest

from decluster.experiments import analyze_contract as experiment


def test_contract_covers_depth_fusion_truncation_and_route_naming():
    artifact = experiment.build_artifact()
    assert set(artifact["depth_sweep"]) == {"1", "2", "3", "4", "5"}
    assert artifact["change_fusion"]["sharpened"] is True
    assert artifact["node_cap"]["cap_is_observable"] is True
    assert artifact["route_diagnostic"] == {
        "present_when_requested": True,
        "canonical_meaning": "provenance_route_accumulation",
    }
    for result in artifact["depth_sweep"].values():
        assert result["fused"]["min_entropy_bits"] <= result["provenance"]["min_entropy_bits"]


def test_reproduce_then_verify_round_trip(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main([
        "verify", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert json.loads(artifact.read_text())["experiment"] == experiment.EXPERIMENT_ID


def test_verify_rejects_modified_artifact():
    artifact = experiment.build_artifact()
    artifact["change_fusion"]["sharpened"] = False
    with pytest.raises(experiment.VerificationError, match="differs"):
        experiment.verify_artifact(artifact)

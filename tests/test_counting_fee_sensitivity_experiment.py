import pytest

from decluster.experiments import counting_fee_sensitivity as experiment


def test_fee_sensitivity_preserves_distinct_counting_objects():
    pytest.importorskip("dss")
    artifact = experiment.build_artifact()
    observations = {row["fee_sat"]: row for row in artifact["observations"]}

    assert observations[0]["router"]["count"] == 2
    assert observations[0]["measured_input_indices"] == [0, 1, 2]
    assert observations[1]["router"]["count"] == 1
    assert observations[1]["measured_input_indices"] == [1, 2]
    assert observations[10]["router"]["count"] == 1
    assert observations[10]["measured_input_indices"] == []


def test_artifact_round_trip(tmp_path):
    pytest.importorskip("dss")
    artifact = tmp_path / "result.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown)
    ]) == 0
    assert experiment.main([
        "verify", "--artifact", str(artifact), "--markdown", str(markdown)
    ]) == 0

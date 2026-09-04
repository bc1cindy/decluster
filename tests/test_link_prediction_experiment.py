import json
from pathlib import Path

import pytest

from decluster.experiments import link_prediction as experiment


ROOT = Path(__file__).resolve().parents[1]


def test_artifact_preserves_configuration_controls_and_limitations():
    artifact = experiment.build_artifact()

    assert artifact["report"]["configuration"]["fixture_seeds"] == [0, 1, 2, 3, 4]
    assert len(artifact["report"]["fixtures"]) == 5
    assert all(len(fixture["runs"]) == 5 for fixture in artifact["report"]["fixtures"])
    assert "not a reproduction" in artifact["limitations"][2]


def test_canonical_report_preserves_the_legacy_measurements():
    legacy = json.loads((ROOT / "results" / "link-prediction.json").read_text())

    assert experiment.build_artifact()["report"] == legacy


def test_verifier_recomputes_the_full_report():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["report"]["fixtures"][0]["runs"][0]["deanonymization"]["auc"] = 1.0

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
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

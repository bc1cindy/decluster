import json
from pathlib import Path

import pytest

from decluster.experiments import boltzmann_fee_audit as experiment


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_report_preserves_all_historical_measurements():
    historical = json.loads(
        (ROOT / "results" / "boltzmann-fee-audit.json").read_text()
    )

    assert experiment.build_artifact()["report"] == historical


def test_artifact_keeps_reference_parity_claim_separate():
    limitations = experiment.build_artifact()["limitations"]

    assert "not general parity" in limitations[3]
    assert "official Boltzmann vectors" in limitations[4]


def test_verifier_recomputes_the_full_report():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["report"]["outcomes"]["fee_tolerant_with_nontrivial_split"] = 0

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

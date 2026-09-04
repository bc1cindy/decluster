import json
from pathlib import Path

from decluster.experiments import subtx_demix as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "subtx-demix-cache-2026-09-04.tar.gz"


def test_snapshot_reproduces_the_canonical_artifact():
    artifact = experiment.build_artifact(SNAPSHOT)
    stored = json.loads(
        (ROOT / "results" / "artifacts" / "subtx-demix-v1.json").read_text()
    )
    assert artifact == stored


def test_joinmarket_mechanism_reproduces_without_claiming_identity_labels():
    artifact = experiment.build_artifact(SNAPSHOT)
    measurement = artifact["measurement"]
    assert len(measurement["joinmarket"]["recovered_inputs"]) == 8
    assert sorted(measurement["joinmarket"]["fees"]) == [191, 413, 458, 559, 623, 636, 687, 973]
    assert artifact["verdicts"]["joinmarket_fixture"] == "reproduced"


def test_unlabelled_cache_cannot_support_the_historical_specificity_claim():
    artifact = experiment.build_artifact(SNAPSHOT)
    measurement = artifact["measurement"]
    assert measurement["eligible_transactions"] == 25
    assert measurement["eligible_with_any_recovery"] == 22
    assert artifact["verdicts"]["ordinary_transaction_specificity"] == "not_tested"
    assert artifact["verdicts"]["wasabi_rounds"] == "not_reproduced"

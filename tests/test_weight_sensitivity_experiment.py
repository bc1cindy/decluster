import json
from pathlib import Path

import pytest

from decluster.experiments import weight_sensitivity as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact(SNAPSHOT)


def test_snapshot_reproduces_the_canonical_artifact(artifact):
    stored = json.loads(
        (ROOT / "results" / "artifacts" / "weight-sensitivity-v1.json").read_text()
    )
    assert artifact == stored


def test_preserved_snapshot_falsifies_monotonicity_but_retains_local_stability(artifact):
    measurement = artifact["measurement"]
    assert measurement["auc_is_monotone_non_decreasing"] is False
    assert measurement["realistic_band_auc_range"] < 0.001
    rows = {row["consistency"]: row for row in measurement["rows"]}
    assert rows[0.99]["auc"] < rows[0.95]["auc"]


def test_result_keeps_attack_and_privacy_score_distinct(artifact):
    assert any("not CoinScore" in limit for limit in artifact["limitations"])

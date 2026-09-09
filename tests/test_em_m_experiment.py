import json
from pathlib import Path

import pytest

from decluster.experiments import em_m as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact(SNAPSHOT)


@pytest.mark.canonical
def test_snapshot_reproduces_the_canonical_artifact(artifact):
    stored = json.loads((ROOT / "results" / "artifacts" / "em-m-v1.json").read_text())
    assert artifact == stored
    assert artifact["measurement"]["transactions"] == 22112


def test_result_reports_difference_without_promoting_it_to_a_verdict(artifact):
    measurement = artifact["measurement"]
    assert measurement["em_minus_fixed_auc"] == pytest.approx(0.0009)
    assert any("without a pre-registered" in item for item in artifact["limitations"])
    assert artifact["historical_comparison"]["status"] == "not_reproduced"


def test_output_names_the_weak_label_and_attack_boundary(artifact):
    markdown = experiment.render_markdown(artifact).lower()
    assert "address-reuse agreement" in markdown
    assert "oracle" not in markdown
    assert any("not CoinScore" in item for item in artifact["limitations"])

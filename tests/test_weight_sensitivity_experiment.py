import json
from pathlib import Path

import pytest

from decluster.experiments import weight_sensitivity as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact(SNAPSHOT)


@pytest.mark.canonical
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


def test_a_dip_is_reported_against_what_the_sample_resolves(artifact):
    """The flag reads the measured sequence; the standard error says whether it means anything.

    The document used to call the historical monotonicity claim *false* on a dip of 0.00055, which
    is 0.18 standard errors at 4,000 pairs per class — reading noise as a finding, in the direction
    that suited the argument.
    """
    measurement = artifact["measurement"]
    assert measurement["auc_standard_error"] > 0
    assert measurement["largest_decrement"] < measurement["auc_standard_error"]
    assert measurement["largest_decrement_in_standard_errors"] < 1.0
    assert artifact["historical_comparison"]["status"] == "not_supported"


def test_the_standard_error_is_the_hanley_mcneil_one():
    from decluster.weight_sensitivity import auc_standard_error

    # A perfect separator has no sampling variance left to report.
    assert auc_standard_error(1.0, 100, 100) == pytest.approx(0.0, abs=1e-12)
    # More pairs, tighter resolution.
    assert auc_standard_error(0.92, 8000, 8000) < auc_standard_error(0.92, 1000, 1000)
    assert auc_standard_error(0.92, 0, 100) is None

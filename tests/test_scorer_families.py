"""The three axis families, and the one property that makes their magnitudes comparable."""
import json
from pathlib import Path

import pytest

from decluster.experiments import scorer_families as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = str(ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz")


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact(SNAPSHOT)


def test_reproduce_then_verify(tmp_path):
    art, markdown = tmp_path / "a.json", tmp_path / "a.md"
    argv = ["--snapshot", SNAPSHOT]
    assert experiment.main(argv + ["reproduce", "--artifact", str(art), "--markdown", str(markdown)]) == 0
    assert experiment.main(argv + ["verify", "--artifact", str(art), "--markdown", str(markdown)]) == 0


def test_only_the_axis_set_differs_between_families(artifact):
    rows = artifact["measurement"]["rows"]
    assert {row["family"] for row in rows} == {"catalogued", "construction_only", "decorrelated"}
    assert len({row["n_pos"] for row in rows}) == 1
    assert len({row["n_neg"] for row in rows}) == 1
    assert [row["axes"] for row in rows] == [23, 18, 14]


def test_the_catalogued_family_agrees_with_the_weight_sweep_at_the_same_consistency(artifact):
    """A second run of the same kernel at 0.95 has to land on the same row, or one of them is wrong."""
    sweep = json.loads((ROOT / "results" / "artifacts" / "weight-sensitivity-v1.json").read_text())
    row = next(r for r in sweep["measurement"]["rows"] if r["consistency"] == 0.95)
    catalogued = next(r for r in artifact["measurement"]["rows"] if r["family"] == "catalogued")
    for key in ("auc", "pos_mean", "neg_mean", "n_pos", "n_neg"):
        assert catalogued[key] == pytest.approx(row[key]), key


def test_dropping_redundant_axes_costs_magnitude(artifact):
    measured = artifact["measurement"]
    assert measured["magnitude_fall_from_catalogued_to_decorrelated"] > 0
    assert measured["auc_rises_as_axes_are_dropped"]


def test_a_tampered_artifact_is_refused(artifact):
    stored = json.loads(json.dumps(artifact))
    stored["measurement"]["rows"][0]["auc"] += 0.01
    with pytest.raises(experiment.VerificationError):
        experiment.verify_artifact(stored, SNAPSHOT)

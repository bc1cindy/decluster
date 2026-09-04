import json
from pathlib import Path

import pytest

from decluster.experiments import bayes_vs_fs as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact(SNAPSHOT)


def test_snapshot_reproduces_the_canonical_artifact(artifact):
    stored = json.loads(
        (ROOT / "results" / "artifacts" / "bayes-vs-fs-v1.json").read_text()
    )
    assert artifact == stored
    assert artifact["dataset"] == "fs-blkcache-2026-09-04-v1"
    assert artifact["measurement"]["pairs"] == {"positive": 4000, "negative": 4000}


def test_experiment_preserves_attack_and_defense_boundary(artifact):
    assert any("not CoinScore" in item for item in artifact["limitations"])
    assert artifact["historical_comparison"]["status"] == "not_reproduced"


def test_axis_rows_name_weak_label_estimate_without_calling_it_an_oracle(artifact):
    rows = artifact["measurement"]["per_axis"]
    assert rows
    assert all("address_reuse_agreement" in row for row in rows)
    assert "oracle" not in experiment.render_markdown(artifact).lower()


def test_verifier_recomputes_instead_of_trusting_stored_values(monkeypatch, artifact):
    monkeypatch.setattr(experiment, "build_artifact", lambda snapshot: artifact)
    changed = {**artifact, "dataset": "wrong"}
    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(changed, SNAPSHOT)

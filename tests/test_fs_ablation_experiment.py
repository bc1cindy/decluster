import json
from pathlib import Path

import pytest

from decluster.experiments import fs_ablation as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


def test_snapshot_reproduces_the_historical_ablation_report():
    historical = json.loads((ROOT / "results" / "fs-ablation.json").read_text())
    artifact = experiment.build_artifact(SNAPSHOT)

    assert artifact["report"] == historical
    assert artifact["dataset"] == "fs-blkcache-2026-09-04-v1"
    assert "duplicates" in artifact["limitations"][3]


def test_verifier_recomputes_the_population_ablation():
    artifact = experiment.build_artifact(SNAPSHOT)
    artifact["report"]["association"]["cluster_threshold"] = 0.9

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(artifact, SNAPSHOT)


def test_cli_reproduces_and_verifies_json_and_markdown(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "--snapshot", str(SNAPSHOT), "reproduce",
        "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main([
        "--snapshot", str(SNAPSHOT), "verify",
        "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0

import json

import pytest

from decluster.experiments import fingerprint_regime as experiment


def test_reproduce_then_verify_snapshot(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    argv = ["--dataset", "tests/fixtures/fingerprint_blkcache_sample.json"]
    assert experiment.main(argv + [
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main(argv + [
        "verify", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0


def test_snapshot_measured_result_does_not_support_stable_conditioner_claim():
    artifact = experiment.build_artifact()
    rows = {row["weight_source"]: row for row in artifact["measurement"]["rows"]}
    measured = rows["snapshot_measured"]
    assert measured["ns_top1"] > measured["fs_top1"]
    assert measured["within_class_gap_mean"] > 0.5


def test_duplicate_transaction_ids_are_rejected(tmp_path):
    dataset = tmp_path / "duplicate.json"
    dataset.write_text(json.dumps([{"txid": "x"}, {"txid": "x"}]), encoding="utf-8")
    with pytest.raises(experiment.VerificationError, match="must be unique"):
        experiment.build_artifact(dataset)

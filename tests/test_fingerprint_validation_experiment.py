import json

import pytest

from decluster.experiments import fingerprint_validation as experiment


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


def test_duplicate_transaction_id_is_rejected(tmp_path):
    dataset = tmp_path / "duplicate.json"
    dataset.write_text(json.dumps([{"txid": "x"}, {"txid": "x"}]), encoding="utf-8")
    with pytest.raises(experiment.VerificationError, match="duplicate transaction id"):
        experiment.build_artifact(dataset)

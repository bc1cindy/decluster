import gzip

import pytest

from decluster.experiments import slice_channels as experiment


def test_reproduce_then_verify_snapshot(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    argv = ["--dataset", "tests/fixtures/slice_a_channels_2016.ndjson.gz"]
    assert experiment.main(argv + [
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main(argv + [
        "verify", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0


def test_empty_snapshot_is_rejected(tmp_path):
    dataset = tmp_path / "empty.ndjson.gz"
    with gzip.open(dataset, "wt", encoding="utf-8"):
        pass
    with pytest.raises(experiment.VerificationError, match="snapshot is empty"):
        experiment.build_artifact(dataset)

import gzip
import json

import pytest

from decluster.experiments import reid as experiment


def test_reproduce_then_verify_snapshot(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "--dataset", "tests/fixtures/reid_sigs.json.gz", "reproduce",
        "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main([
        "--dataset", "tests/fixtures/reid_sigs.json.gz", "verify",
        "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0


def test_seeded_sampling_is_independent_of_serialized_object_order(tmp_path):
    first = {
        "a": {"sig": {"x": 1.0, "y": 2.0, "z": 3.0, "w": 4.0}},
        "b": {"sig": {"q": 1.0, "r": 2.0, "s": 3.0, "t": 4.0}},
    }
    second = {
        "b": {"sig": {"t": 4.0, "s": 3.0, "r": 2.0, "q": 1.0}},
        "a": {"sig": {"w": 4.0, "z": 3.0, "y": 2.0, "x": 1.0}},
    }
    paths = []
    for index, value in enumerate((first, second)):
        path = tmp_path / f"{index}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as target:
            json.dump(value, target)
        paths.append(path)
    assert experiment.build_artifact(paths[0]) == experiment.build_artifact(paths[1])


def test_invalid_signature_weight_is_rejected(tmp_path):
    dataset = tmp_path / "bad.json.gz"
    with gzip.open(dataset, "wt", encoding="utf-8") as target:
        json.dump({"a": {"sig": {"x": -1}}, "b": {"sig": {"y": 1}}}, target)
    with pytest.raises(experiment.VerificationError, match="invalid signature entry"):
        experiment.build_artifact(dataset)

import gzip
import json

import pytest

from decluster.def1_sparsity import cosine
from decluster.experiments import ancestry_sparsity as experiment


def test_sparse_inverted_index_matches_pairwise_cosine():
    signatures = {
        "a": {"x": 1.0, "y": 2.0},
        "b": {"x": 3.0},
        "c": {"z": 4.0},
    }
    actual = experiment._nearest_cosines(signatures)
    assert actual["a"] == pytest.approx(cosine(signatures["a"], signatures["b"]))
    assert actual["b"] == pytest.approx(cosine(signatures["b"], signatures["a"]))
    assert actual["c"] == 0.0


def test_stored_comparison_values_are_not_reused(tmp_path):
    dataset = tmp_path / "signatures.json.gz"
    records = {
        "a": {"sig": {"x": 1.0}, "top": 0.75},
        "b": {"sig": {"y": 1.0}, "top": 0.75},
    }
    with gzip.open(dataset, "wt", encoding="utf-8") as target:
        json.dump(records, target)
    artifact = experiment.build_artifact(dataset)
    assert artifact["nearest_neighbour_cosine"]["median"] == 0.0
    assert artifact["stored_top_context"]["different_from_snapshot_recomputation"] == 2


def test_reproduce_then_verify_real_snapshot(tmp_path):
    dataset = "tests/fixtures/reid_sigs.json.gz"
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "reproduce", "--dataset", dataset, "--artifact", str(artifact),
        "--markdown", str(markdown),
    ]) == 0
    assert experiment.main([
        "verify", "--dataset", dataset, "--artifact", str(artifact),
        "--markdown", str(markdown),
    ]) == 0

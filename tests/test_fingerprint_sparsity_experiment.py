import copy
import json

import pytest

from decluster.experiments import fingerprint_sparsity as experiment


def test_reconstructs_published_whole_window_column():
    artifact = experiment.build_artifact()
    measurement = artifact["measurement"]
    assert artifact["window"]["transactions"] == 98_179_414
    assert round(measurement["class_size_shares"]["exactly 1"] * 100, 3) == 0.009
    assert round(measurement["class_size_shares"][">=100,000"] * 100, 3) == 75.552
    assert round(measurement["share_below_10"] * 100, 3) == 0.061
    assert round(measurement["share_below_100"] * 100, 3) == 0.413
    assert len(artifact["cross_check"]["consistent_conditional_partitions"]) >= 2


def test_disagreeing_conditional_partition_is_refused(tmp_path):
    with open(experiment.DEFAULT_DATASET, encoding="utf-8") as dataset:
        source = json.load(dataset)
    corrupted = copy.deepcopy(source)
    axis = sorted(corrupted["cond"])[0]
    value = sorted(corrupted["cond"][axis])[0]
    corrupted["cond"][axis][value]["buckets"]["exactly 1"] += 1
    path = tmp_path / "corrupted.json"
    path.write_text(json.dumps(corrupted), encoding="utf-8")
    with pytest.raises(experiment.VerificationError, match="covers"):
        experiment.build_artifact(path)


def test_markdown_is_canonical(tmp_path):
    artifact = experiment.build_artifact()
    artifact_path = tmp_path / "artifact.json"
    markdown_path = tmp_path / "result.md"
    from decluster.result_artifacts import write_canonical_json

    write_canonical_json(artifact_path, artifact)
    markdown_path.write_text(experiment.render_markdown(artifact), encoding="utf-8")
    assert experiment.main([
        "--dataset", experiment.DEFAULT_DATASET, "verify",
        "--artifact", str(artifact_path), "--markdown", str(markdown_path),
    ]) == 0

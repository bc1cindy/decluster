import copy
import json

import pytest

from decluster.experiments import attribute_drift as experiment


def _row(artifact, axis):
    return next(row for row in artifact["measurement"]["axes"] if row["axis"] == axis)


@pytest.mark.parametrize("axis, expected", [
    ("nlocktime", (0.009, 0.011, 0.013, 0.018, 0.86)),
    ("low_r", (0.038, 0.052, 0.090, 0.155, 1.04)),
    ("version", (0.029, 0.026, 0.042, 0.070, 0.75)),
])
def test_preserved_projection_reproduces_selected_published_rows(axis, expected):
    row = _row(experiment.build_artifact(), axis)
    observed = tuple(round(row["drift"][str(gap)], 3) for gap in (1, 7, 30, 120))
    observed += (round(row["weekly_gain"], 2),)
    assert observed == expected


def test_volume_is_reconstructed_consistently_from_all_templates():
    artifact = experiment.build_artifact()
    volume = artifact["measurement"]["volume_range"]
    assert volume["minimum"] > 0
    assert volume["maximum"] >= volume["minimum"]
    assert len(artifact["measurement"]["volume_coupling"]) > 1
    assert artifact["window"]["transactions"] == 98_179_414


def test_inconsistent_template_volume_is_refused(tmp_path):
    with open(experiment.DEFAULT_DATASET, encoding="utf-8") as dataset:
        source = json.load(dataset)
    corrupted = copy.deepcopy(source)
    template = sorted(corrupted["template_series"])[0]
    corrupted["template_series"][template][0]["matches"] += 1
    path = tmp_path / "corrupted.json"
    path.write_text(json.dumps(corrupted), encoding="utf-8")
    with pytest.raises(experiment.VerificationError, match="reconstruct volume|inconsistent volume"):
        experiment.build_artifact(path)

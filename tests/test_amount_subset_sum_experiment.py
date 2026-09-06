import json

import pytest

from decluster.experiments import amount_subset_sum as experiment


def test_report_preserves_published_counting_outcomes():
    pytest.importorskip("dss")
    report = experiment.build_report()

    assert report["population"] == {"multi_input": 1428, "maximum_inputs": 16}
    assert report["outcomes"] == {
        "by_kind": {"exact": 1303, "unknown": 125},
        "guaranteed_nonzero_log_w": 80,
        "exact_zero": 1223,
    }


def test_artifact_keeps_counting_objects_distinct(monkeypatch):
    monkeypatch.setattr(experiment, "build_report", lambda _dataset: {})
    limitations = experiment.build_artifact("unused")["limitations"]

    assert "not a Maurer mapping count" in limitations[0]
    assert "does not compute pairwise links" in limitations[5]


def test_verifier_rejects_changed_measurement(monkeypatch):
    artifact = {
        "schema_version": 1,
        "experiment": experiment.EXPERIMENT_ID,
        "value": 2,
    }
    monkeypatch.setattr(experiment, "build_artifact", lambda _dataset: {**artifact, "value": 1})

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(artifact, dataset="unused")

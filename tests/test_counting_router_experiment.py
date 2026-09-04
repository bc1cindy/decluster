import pytest

from decluster.experiments import counting_router as experiment


def test_report_preserves_current_router_outcomes():
    report = experiment.build_report()

    assert report["population"] == {"multi_input_transactions": 1428}
    assert report["current_router"] == {
        "by_method_and_kind": {
            "none:unknown": 1333,
            "radix:exact": 19,
            "sparse:exact": 60,
            "sparse:lower_bound": 16,
        },
        "guaranteed_nonzero_log_w": 95,
    }
    assert report["radix_precondition_audit"] == {
        "precondition_applies": 20,
        "raw_positive": 533,
        "raw_positive_without_precondition": 514,
    }


def test_artifact_keeps_objects_and_scope_distinct(monkeypatch):
    monkeypatch.setattr(experiment, "build_report", lambda _dataset: {})
    limitations = experiment.build_artifact("unused")["limitations"]

    assert "not a mapping count" in limitations[0]
    assert "outside this run" in limitations[4]
    assert "not a privacy score" in limitations[5]


def test_verifier_rejects_changed_measurement(monkeypatch):
    artifact = {"schema_version": 1, "experiment": experiment.EXPERIMENT_ID, "value": 2}
    monkeypatch.setattr(experiment, "build_artifact", lambda _dataset: {**artifact, "value": 1})
    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(artifact, dataset="unused")

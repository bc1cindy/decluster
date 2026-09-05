import pytest

from decluster.experiments import amount_per_coin as experiment


def test_report_preserves_published_per_coin_outcomes():
    report = experiment.build_report()

    assert report["population"] == {
        "transactions": 1428,
        "inputs": 17520,
        "outputs": 6106,
        "coins": 23626,
    }
    assert report["per_coin_density"]["reachable"] == {
        "input": 316,
        "output": 972,
        "total": 1288,
    }
    assert report["ungated_diagnostic"] == {
        "candidate_transactions": 95,
        "candidates": {"input": 60, "output": 258, "total": 318},
    }
    assert report["transaction_gated"] == {
        "resolved_transactions": 82,
        "candidate_transactions": 62,
        "candidates": {"input": 18, "output": 83, "total": 101},
        "candidates_with_exact_transaction_count": {
            "input": 0,
            "output": 61,
            "total": 61,
        },
    }
    # The gate resolves fewer transactions than the diagnostic enumerates, and no
    # candidate carries an exact transaction count: the radix tier is a diagnostic.
    assert report["transaction_gated"]["resolved_transactions"] < (
        report["ungated_diagnostic"]["candidate_transactions"]
    )


def test_artifact_keeps_diagnostic_and_gate_semantics_distinct(monkeypatch):
    monkeypatch.setattr(experiment, "build_report", lambda _dataset, _threshold: {})
    artifact = experiment.build_artifact("unused", 1.0)

    assert "different objects" in artifact["limitations"][2]
    assert "does not make" in artifact["limitations"][3]
    assert "separate identities" in artifact["limitations"][4]


def test_verifier_rejects_changed_measurement(monkeypatch):
    artifact = {
        "schema_version": 1,
        "experiment": experiment.EXPERIMENT_ID,
        "value": 2,
    }
    monkeypatch.setattr(
        experiment,
        "build_artifact",
        lambda _dataset, _threshold: {**artifact, "value": 1},
    )

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(artifact, dataset="unused")


def test_non_finite_threshold_is_rejected():
    with pytest.raises(SystemExit, match="must be finite"):
        experiment.main(["--cut-threshold", "nan", "verify", "--artifact", "unused"])

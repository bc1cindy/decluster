import pytest

pytest.importorskip("dss", reason="DSS restricted-family artifact requires the exact extra")

from decluster.experiments import amount_mapping_family as experiment


def test_report_preserves_published_mapping_family_outcomes():
    report = experiment.build_report()

    assert report["outcomes"] == {
        "answered": 223,
        "refused": 26,
        "timed_out": 1,
        "failed": 0,
    }
    assert report["restricted_family"] == {
        "entropy_bins_bits": {
            "zero": 221,
            "above_zero_to_four": 2,
            "above_four": 0,
        },
        "non_derived_mappings": 227,
        "certain_input_output_links": 1471,
    }


def _completed_context(result):
    class Process:
        def start(self):
            pass

        def join(self, _timeout=None):
            pass

        def is_alive(self):
            return False

    class Queue:
        def get(self, timeout):
            return "answered", result

        def close(self):
            pass

    class FakeContext:
        def Queue(self, maxsize):
            return Queue()

        def Process(self, target, args):
            return Process()

    return FakeContext()


def test_bounded_analysis_distinguishes_legacy_refusal(monkeypatch):
    monkeypatch.setattr(
        experiment.multiprocessing, "get_context", lambda _method: _completed_context(None)
    )
    assert experiment._bounded_analysis([1], [1], 1.0) == ("refused", None)


def test_bounded_analysis_reads_structured_dss_refusal(monkeypatch):
    refusal = {"status": "refused", "reason": "size_guard"}
    monkeypatch.setattr(
        experiment.multiprocessing, "get_context", lambda _method: _completed_context(refusal)
    )
    assert experiment._bounded_analysis([1], [1], 1.0) == ("refused", None)


def test_artifact_limits_claims_to_restricted_family(monkeypatch):
    monkeypatch.setattr(experiment, "build_report", lambda _dataset, _cap, _wall: {})
    limitations = experiment.build_artifact("unused", 1, 1.0)["limitations"]

    assert "strict sub-family" in limitations[0]
    assert "not a posterior" in limitations[1]
    assert "only within" in limitations[2]


def test_verifier_rejects_changed_measurement(monkeypatch):
    artifact = {"schema_version": 1, "experiment": experiment.EXPERIMENT_ID, "value": 2}
    monkeypatch.setattr(
        experiment, "build_artifact",
        lambda _dataset, _cap, _wall: {**artifact, "value": 1},
    )
    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(artifact, dataset="unused", cap=1, wall_seconds=1.0)

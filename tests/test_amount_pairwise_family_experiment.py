import pytest

from decluster.experiments import amount_pairwise_family as experiment


def test_report_preserves_published_pairwise_family_outcomes():
    report = experiment.build_report()

    assert report["population"] == {
        "selected_transactions": 300,
        "selected_input_rows": 3384,
        "selected_outputs": 1540,
        "selection": "first complete multi-input transactions in source order",
    }
    assert report["outcomes"] == {
        "answered": 271,
        "refused": 27,
        "timed_out": 2,
        "failed": 0,
    }
    assert report["restricted_family_rows"] == {
        "returned": 914,
        "nonempty_support": 914,
        "singleton_support": 367,
        "full_output_support": 898,
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


def test_bounded_matrix_distinguishes_refusal(monkeypatch):
    monkeypatch.setattr(
        experiment.multiprocessing, "get_context", lambda _method: _completed_context(None)
    )
    assert experiment._bounded_matrix([1], [1], 1.0) == ("refused", None)


def test_artifact_limits_claims_to_restricted_family(monkeypatch):
    monkeypatch.setattr(experiment, "build_report", lambda _dataset, _cap, _wall: {})
    limitations = experiment.build_artifact("unused", 1, 1.0)["limitations"]

    assert "restricted mapping family" in limitations[0]
    assert "not a globally deterministic" in limitations[1]
    assert "false certainties" in limitations[2]


def test_verifier_rejects_changed_measurement(monkeypatch):
    artifact = {"schema_version": 1, "experiment": experiment.EXPERIMENT_ID, "value": 2}
    monkeypatch.setattr(
        experiment, "build_artifact",
        lambda _dataset, _cap, _wall: {**artifact, "value": 1},
    )
    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(artifact, dataset="unused", cap=1, wall_seconds=1.0)

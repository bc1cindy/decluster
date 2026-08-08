"""Robust oracle layer: dss_link_oracle panic-safety, and the in-process default /
opt-in subprocess oracles built on top of it."""
import decluster.oracle as oracle
import examples.anonymity_set as anonymity_set_example
from decluster import ancestry


class _BoomPanic(BaseException):
    """Stand-in for pyo3_runtime.PanicException: a BaseException, not an Exception."""


def test_dss_link_oracle_survives_base_exception_panic(monkeypatch):
    class _FakeDss:
        @staticmethod
        def pairwise_link_prob(inputs, outputs, budget_ms):
            raise _BoomPanic("assertion failed: set.len() <= 64")

    import sys
    monkeypatch.setitem(sys.modules, "dss", _FakeDss())

    assert ancestry.dss_link_oracle([1], [1]) is None


def test_bounded_link_oracle_is_callable_and_tolerant():
    for budget_ms in (500, 6000):
        link = oracle.bounded_link_oracle(budget_ms)
        assert callable(link)
        result = link([100], [100])
        assert result is None or isinstance(result, list)


def test_subprocess_link_oracle_importable_and_reexported():
    assert callable(oracle.subprocess_link_oracle)
    assert anonymity_set_example.hard_bounded_link_oracle is oracle.subprocess_link_oracle

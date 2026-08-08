import pytest

from decluster import counting


def test_w_total_delegates_to_dss_and_counts_small():
    pytest.importorskip("dss")
    rep = counting.w_total([100, 200, 300], [150, 150, 200, 100])
    assert rep["kind"] == "exact"
    assert rep["count"] == 6
    assert rep["log_w"] == pytest.approx(1.791759469228055)
    assert rep["method"] in ("brute", "dp", "sparse")   # an exact tier


def test_w_total_dense_coinjoin_is_exact_not_unknown():
    # The 16-in/60-out dense mix that the old Python size-gate sent to Sasamoto (-> unknown): the dss
    # cascade counts it exactly (N=16 -> brute), so w_total returns a real count.
    pytest.importorskip("dss")
    ins = [5000000, 5000000, 3000000, 2000000] * 4
    outs = [1000000] * 60
    rep = counting.w_total(ins, outs)
    assert rep["count"] is not None
    assert rep["log_w"] is not None
    assert rep["kind"] == "exact"


def test_w_total_swallows_panic_from_dss(monkeypatch):
    # w_total delegates to dss.w_count; if that ever raises (e.g. a Rust panic surfaced as a
    # BaseException), w_total degrades to unknown rather than crashing the caller.
    import dss

    class _Panic(BaseException):
        pass

    monkeypatch.setattr(dss, "w_count", lambda i, o: (_ for _ in ()).throw(_Panic()))
    assert counting.w_total([100, 200], [100, 200]) == {"kind": "unknown", "count": None, "log_w": None}

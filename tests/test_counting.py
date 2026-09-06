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
    pytest.importorskip("dss")
    import dss

    class _Panic(BaseException):
        pass

    monkeypatch.setattr(dss, "w_count", lambda i, o: (_ for _ in ()).throw(_Panic()))
    assert counting.w_total([100, 200], [100, 200]) == {"kind": "unknown", "count": None, "log_w": None}


def test_a_wide_transaction_is_refused_rather_than_attempted():
    """The counting cascade takes no budget and does not bound itself: past twenty inputs it stops
    returning, and a hang inside Rust is caught by neither the panic guard nor a Python alarm. The
    only bound is declining to make the call, which reads as `unknown` — multiplicity 1, the safe
    direction for a refuse-only channel."""
    pytest.importorskip("dss")
    from decluster import counting
    wide = counting.w_total(list(range(1, 40)), [100, 200])
    assert wide == {"kind": "unknown", "count": None, "log_w": None}
    assert counting.guaranteed_log_w(wide) is None
    # the cap is a parameter, not a hard-coded refusal
    assert counting.w_total([1, 2, 3], [3, 3], max_size=3)["kind"] == "exact"


def test_an_exact_zero_does_not_corroborate_a_cut():
    """A fee-paying transaction has no exactly-balancing input subset, so the fee-blind count
    completes at zero. That is the counter finding nothing, not finding certainty."""
    from decluster.cost import amount_cuts
    oracle = lambda i, o: {"coins": [{"role": "in", "index": 0, "value": 10, "log_w": 0.1}]}
    zero = lambda i, o: {"kind": "exact", "count": 0, "log_w": None}
    found = lambda i, o: {"kind": "exact", "count": 3, "log_w": 1.58}
    # an exact zero resolved nothing, so there is nothing to apportion at all
    assert amount_cuts([10, 20], [25], oracle, count_oracle=zero) == []
    assert amount_cuts([10, 20], [25], oracle, count_oracle=found)[0].transaction_count_exact is True


def test_the_per_coin_path_returns_where_the_whole_tx_count_will_not():
    """The whole-transaction count is width-bounded; the per-coin path is not. Neither invents a
    measurement for a coin it could not reach — unreachable coins are simply absent."""
    pytest.importorskip("dss")
    from decluster import counting
    ins = [680849, 390740, 434988, 225790, 300000, 120000, 90000]
    outs = [104781, 2500000]
    assert counting.w_total(ins, outs)["count"] == 0        # fee-blind: nothing balances exactly
    assert counting.per_coin_log_w(ins, outs) == {}          # and no coin was reachable either

    wide = list(range(1_000_000, 1_000_000 + 60))            # past the whole-tx count's width limit
    assert counting.w_total(wide, [100, 200])["kind"] == "unknown"
    counting.per_coin_log_w(wide, [100, 200])                # returns rather than hangs


def test_the_router_skips_brute_and_bounds_the_convolution():
    """Brute force is the convolution below its crossover, so the order is radix then the
    convolution bounded by the knee. The crate's own cascade instead tries brute first and hands the
    convolution an unbounded subset size, which is why it does not return past twenty inputs."""
    pytest.importorskip("dss")
    from decluster import counting
    wide = [1_000_000 + i for i in range(60)]
    r = counting.count_w(wide, [30_000_000, 100])
    assert r["method"] in ("radix", "sparse", "none")
    assert counting.w_total(wide, [30_000_000, 100])["kind"] == "unknown"   # the cascade declines


def test_a_tier_that_counted_nothing_does_not_short_circuit_the_next():
    """An exact zero is the absence of an answer, not an answer of no ambiguity. The radix path
    returns one on 63% of real multi-input transactions; accepting it would stop the routing."""
    from decluster.counting import _resolved
    assert _resolved(lambda: {"kind": "exact", "count": 0, "log_w": None}) is None
    assert _resolved(lambda: {"kind": "unknown", "count": None, "log_w": None}) is None
    assert _resolved(lambda: {"kind": "exact", "count": 4, "log_w": 2.0})["count"] == 4


def test_the_saddle_point_is_available_but_never_a_tier():
    """It estimates a magnitude where the exact tiers return a truncated floor, and those are
    different readings — chaining it as an automatic upgrade would let an estimate stand where a
    guarantee was asked for. So it is reachable on purpose, not through the routing."""
    pytest.importorskip("dss")
    from decluster import counting
    dense = [1000 + i for i in range(200)]          # deep in the regime the estimator wants
    assert counting.is_dense(dense, [50_000, 50_000]) is True
    assert counting.count_w(dense, [50_000, 50_000])["method"] != "sasamoto"
    assert hasattr(counting, "saddle_point_log_w")
    assert counting.saddle_point_log_w([1, 2, 3], [3]) is None      # declines, never invents


def test_the_denominational_diagnostic_needs_a_repeated_denomination():
    """It counts the ways a repeated denomination permutes among participants, so it says nothing
    unless one repeats. The crate returns a number either way and leaves the precondition to the
    caller: unguarded it answers on 64 of 1,428 real multi-input transactions, 51 of which carry no
    repeated value."""
    pytest.importorskip("dss")
    from decluster import counting
    assert counting.radix_applies([5_000, 5_000, 5_000, 1_234]) is True
    assert counting.radix_applies([600_000, 400_000]) is False
    assert counting.radix_applies([5_000, 5_000, 1_234]) is False      # twice is not a series
    assert counting.radix_applies([]) is False
    ordinary = counting.count_w([500_000, 300_000, 200_000], [600_000, 400_000])
    assert ordinary["method"] != "radix"


def test_the_denominational_count_never_passes_the_guarantee_gate():
    """It is a function of the outputs alone and moves under a rescaling that leaves the mapping
    count fixed, so it bounds the transaction's ambiguity in neither direction. The crate tags it
    `diagnostic`; the gate refuses that kind, and `cost.amount_cuts` cannot read it as exact."""
    pytest.importorskip("dss")
    import dss
    from decluster import counting
    denominated = [5_000, 5_000, 5_000]
    reading = dss.radix_mappings(denominated, counting.KNEE)
    assert reading["kind"] == "diagnostic"
    # One value repeated three times contributes 3! once, not once per coin, and a decomposition
    # naming a denomination no output carries has no subset to exchange.
    assert reading["count"] == 6
    assert dss.radix_mappings(denominated + [5_512], counting.KNEE)["count"] == 6
    assert counting.guaranteed_log_w(reading) is None

    routed = counting.count_w([15_000], denominated)
    assert routed["method"] == "radix"
    assert counting.guaranteed_log_w(routed) is None


def test_a_repeated_value_is_not_automatically_a_denomination():
    """The classification separates by kind of value first: a denomination is a single digit times
    a power of one of the bases. A value that repeats but is not one of those is not a series, and
    counting its repeats towards the bound counts the wrong thing."""
    from decluster import counting
    assert counting.radix_series(5_000_000) == (10, 6, 5)
    assert counting.radix_series(1 << 20) == (2, 20, 1)
    assert counting.radix_series(2_500_000) is None        # 25 x 10^5: two digits, not one
    assert counting.radix_series(104_781) is None
    assert counting.radix_applies([5_000_000] * 3 + [123]) is True
    assert counting.radix_applies([2_500_000] * 3 + [123]) is False   # repeats, not a denomination


def test_mapping_entropy_answers_on_a_fee_paying_transaction():
    """Entropy over DSS's mapping family is distinct from a mapping count. It balances the fee in
    as an extra output, so unlike the counts it answers when a fee is paid. Zero means one reading
    survives in this restricted family, not that ownership is globally proven."""
    pytest.importorskip("dss")
    from decluster import counting
    ins = [500_000, 300_000, 200_000]
    for fee in (0, 5_000, 50_000):
        r = counting.mapping_entropy(ins, [600_000, 400_000 - fee])
        assert r is not None
        assert r["entropy"] == 0.0 and r["n_non_derived"] == 1
        assert r["deterministic_links"]              # every mapping in this family shares links
        assert all(o < 2 for _, o in r["deterministic_links"])   # the fee column is dropped


def test_mapping_entropy_turns_structured_refusal_into_no_measurement(monkeypatch):
    import sys
    from decluster import counting

    class RefusingDss:
        @staticmethod
        def mapping_analysis(inputs, outputs, budget_ms):
            return {"status": "refused", "reason": "size_guard"}

    monkeypatch.setitem(sys.modules, "dss", RefusingDss)
    assert counting.mapping_entropy([1], [1]) is None

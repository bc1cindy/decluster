"""`analyze()` and `report()` are documented as one walk read two ways. This pins that: on one
fixture, with no oracle passed, both facades must produce the same provenance distribution.

It would have failed while `report`/`ancestry` defaulted to the value-flow oracle and `analyze`
still defaulted to the subset-sum one."""
import pytest

from decluster import ancestry, path_count, report
from decluster.analyze import analyze


def _coinbase(value):
    return {"vin": [{"is_coinbase": True}], "vout": [{"value": value}]}


def _vin(txid, value):
    return {"is_coinbase": False, "txid": txid, "vout": 0, "prevout": {"value": value}}


def _txs():
    return {
        "C": {"txid": "C", "vin": [_vin("P", 3), _vin("R", 5)],
              "vout": [{"value": 3, "scriptpubkey_type": "v0_p2wpkh"},
                       {"value": 5, "scriptpubkey_type": "v0_p2wpkh"}]},
        "P": _coinbase(3),
        "R": _coinbase(5),
    }


# The amount channel is not under test here and its default count oracle needs the compiled `dss`
# extension; refusing at the transaction level keeps this a pure provenance-walk comparison.
def _no_counts(inputs, outputs):
    return {}


def test_analyze_and_report_agree_on_the_default_walk():
    txs = _txs()
    fetch = lambda t: txs[t]

    a = analyze(txs["C"], depth=6, fetch=fetch, subjective=False)
    r = report.report(txs["C"], depth=6, fetch=fetch, subjective=False,
                      count_oracle=_no_counts)

    assert set(a) == set(r["targets"])
    for vout in a:
        prov, target = a[vout]["provenance"], r["targets"][vout]
        assert prov["shannon"] == pytest.approx(target["shannon"])
        assert prov["min_entropy"] == pytest.approx(target["min_entropy"])
        assert prov["n_absorbers"] == target["n_absorbers"]


def test_the_agreed_walk_is_the_value_flow_one():
    txs = _txs()
    fetch = lambda t: txs[t]
    expected = ancestry.value_flow_signature(("C", 0), depth=6, fetch=fetch)

    assert expected == pytest.approx({("P", 0): 0.375, ("R", 0): 0.625})
    a = analyze(txs["C"], targets=[0], depth=6, fetch=fetch, subjective=False)
    assert a[0]["provenance"]["origins"] == pytest.approx(expected)


def test_no_facade_reaches_the_subset_sum_oracle_by_default(monkeypatch):
    txs = _txs()
    fetch = lambda t: txs[t]

    def fail_if_called(*args, **kwargs):
        raise AssertionError("the subset-sum oracle is no longer any facade's default")

    monkeypatch.setattr(ancestry, "dss_link_oracle", fail_if_called)

    analyze(txs["C"], depth=6, fetch=fetch, subjective=False)
    report.report(txs["C"], depth=6, fetch=fetch, subjective=False, count_oracle=_no_counts)
    path_count.path_count_anonymity(("C", 0), depth=6, fetch=fetch)

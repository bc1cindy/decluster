import pytest

from decluster import cost


class _FakeCombiner:
    def __init__(self, bits): self._bits = bits
    def score(self, a, b): return self._bits


def test_leak_bits_delegates_to_combiner():
    tx_a, tx_b = {"txid": "a"}, {"txid": "b"}
    assert cost.leak_bits(tx_a, tx_b, _FakeCombiner(13.9)) == 13.9


def _fake_oracle(coins, kappa=0.5):
    return lambda inputs, outputs: {"kappa": kappa, "coins": coins}


def test_amount_cuts_fires_only_on_low_w():
    coins = [
        {"role": "maker", "index": 0, "value": 100, "log_w": 0.0, "kappa_c": 0.9},   # low W -> cut
        {"role": "maker", "index": 1, "value": 200, "log_w": 8.0, "kappa_c": 0.9},   # high W -> ambiguous, no cut
    ]
    cuts = cost.amount_cuts([100, 200], [150, 150], _fake_oracle(coins), cut_threshold=1.0)
    assert [c.index for c in cuts] == [0]
    assert cuts[0].value == 100


def test_amount_cuts_dense_returns_none():
    coins = [{"role": "mix", "index": i, "value": 100, "log_w": 12.0, "kappa_c": 0.9} for i in range(3)]
    assert cost.amount_cuts([1, 2, 3], [1, 1, 1], _fake_oracle(coins)) == []


def test_amount_cuts_skips_unreachable_none_log_w():
    # a coin unreachable within the truncation -> log_w None -> skipped, not cut (and no crash)
    coins = [
        {"role": "in", "index": 0, "value": 100, "log_w": None, "kappa_c": 0.9},   # unreachable -> skip
        {"role": "in", "index": 1, "value": 200, "log_w": 0.0, "kappa_c": 0.9},     # low -> cut
    ]
    cuts = cost.amount_cuts([100, 200], [150, 150], _fake_oracle(coins))
    assert [c.index for c in cuts] == [1]


def test_topology_bits_disjoint_penalises():
    # two clusters with disjoint counterparties -> negative (refuse) weight
    neigh = {"A": {"x"}, "B": {"y"}}
    assert cost.topology_bits(["A"], ["B"], neigh) < 0


def test_topology_bits_shared_rare_corroborates():
    # a shared, rare counterparty -> positive weight
    neigh = {"A": {"rare"}, "B": {"rare"}, "C": {"c"}, "D": {"d"}}
    assert cost.topology_bits(["A"], ["B"], neigh) > 0


def test_ancestry_entropy_is_wired_not_a_stub():
    # the path-counting target is now the ancestry engine; it no longer raises NotImplementedError
    assert hasattr(cost, "ancestry_entropy")
    assert not hasattr(cost, "privacy_of_transaction")


def test_construction_cost_is_a_stub():
    # composition deferred: construction_cost raises until the metric design lands
    with pytest.raises(NotImplementedError):
        cost.construction_cost(leak=1.0, topology=0.0)


def test_dss_oracle_shape_when_available():
    dss = pytest.importorskip("dss")
    rep = cost.dss_oracle([100, 200], [150, 150])
    assert "kappa" in rep and "coins" in rep
    assert all({"index", "value", "log_w", "kappa_c"} <= set(c) for c in rep["coins"])

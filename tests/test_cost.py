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


def _resolved(kind="lower_bound", count=3, log_w=1.58):
    """A whole-transaction reading that resolved, which step three is gated on."""
    return lambda inputs, outputs: {"kind": kind, "count": count, "log_w": log_w}


def test_amount_cuts_fires_only_on_low_w():
    coins = [
        {"role": "maker", "index": 0, "value": 100, "log_w": 0.0, "kappa_c": 0.9},   # low W -> cut
        {"role": "maker", "index": 1, "value": 200, "log_w": 8.0, "kappa_c": 0.9},   # high W -> ambiguous, no cut
    ]
    cuts = cost.amount_cuts([100, 200], [150, 150], _fake_oracle(coins), cut_threshold=1.0,
                            count_oracle=_resolved())
    assert [c.index for c in cuts] == [0]
    assert cuts[0].role == "maker"
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
    cuts = cost.amount_cuts([100, 200], [150, 150], _fake_oracle(coins),
                            count_oracle=_resolved())
    assert [c.index for c in cuts] == [1]


def test_amount_cuts_on_a_lower_bound_reading_stays_a_candidate():
    """The transaction resolved, so the coins can be read — but a floor is not an exact count and
    the cut it supports is a candidate, not a rigorous one."""
    coins = [{"role": "in", "index": 0, "value": 100, "log_w": 0.0, "kappa_c": 0.9}]
    cuts = cost.amount_cuts([100, 200], [150, 150], _fake_oracle(coins),
                            count_oracle=_resolved(kind="lower_bound"))
    assert cuts[0].transaction_count_exact is False


def test_amount_cuts_preserves_exact_transaction_gate_provenance():
    coins = [{"role": "in", "index": 0, "value": 100, "log_w": 0.0, "kappa_c": 0.9}]
    exact_count_oracle = lambda inputs, outputs: {"kind": "exact", "count": 3, "log_w": 1.58}
    cuts = cost.amount_cuts([100, 200], [150, 150], _fake_oracle(coins),
                             count_oracle=exact_count_oracle)
    assert cuts[0].transaction_count_exact is True


def test_no_cuts_where_the_transaction_as_a_whole_did_not_resolve():
    """Apportioning ambiguity across the coins of a transaction whose ambiguity did not resolve is
    apportioning nothing. Measured on a real slice, a third of the transactions the per-coin oracle
    spoke for had no transaction-level reading behind them."""
    coins = [{"role": "in", "index": 0, "value": 100, "log_w": 0.0, "kappa_c": 0.9}]
    unresolved = lambda inputs, outputs: {"kind": "unknown", "count": None, "log_w": None}
    assert cost.amount_cuts([100, 200], [150, 150], _fake_oracle(coins),
                            count_oracle=unresolved) == []


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


def test_construction_cost_returns_structured_terms_with_path_count_target():
    # the target is no longer missing (path_count_anonymity is wired) -> no raise, structured terms
    from decluster.path_count import path_count_anonymity
    terms = cost.construction_cost(leak=1.0, topology=0.0, target_fn=path_count_anonymity)
    assert terms == {"leak": 1.0, "topology": 0.0, "target": path_count_anonymity}


def test_construction_cost_default_target_is_path_count_anonymity():
    from decluster.path_count import path_count_anonymity
    terms = cost.construction_cost(leak=1.0, topology=0.0)
    assert terms["target"] is path_count_anonymity


def test_construction_cost_combine_still_raises_citing_only_combination():
    # channel COMBINATION into one scalar is the only remaining deferred piece
    with pytest.raises(NotImplementedError, match="combin"):
        cost.construction_cost(leak=1.0, topology=0.0, combine=True)


def test_dss_oracle_shape_when_available():
    dss = pytest.importorskip("dss")
    rep = cost.dss_oracle([100, 200], [150, 150])
    assert "kappa" in rep and "coins" in rep
    assert all({"index", "value", "log_w", "kappa_c"} <= set(c) for c in rep["coins"])


def test_density_gate_kappa_vs_kappa_c_orients_dense_and_sparse():
    """The density gate PAPER.md §2 names: the dss magnitude engine draws the dense/decidable
    boundary at kappa = log2(L)/N < kappa_c (Sasamoto eq 4.3). Pin its orientation on the exposed
    per_coin_density variables: a near-uniform (dense) instance lands kappa below the per-coin
    kappa_c; a spread (sparse/decidable) instance lands it above. This is the counting-estimator
    validity gate, not the clusterer's refuse threshold (which reads log_w)."""
    dss = pytest.importorskip("dss")
    dense = dss.per_coin_density([100 + (k % 7) for k in range(40)], [2000, 1900])
    assert dense["kappa"] < dense["coins"][0]["kappa_c"]      # kappa < kappa_c -> dense regime
    sparse = dss.per_coin_density([3, 7, 19, 41], [10, 60])
    assert sparse["kappa"] > sparse["coins"][0]["kappa_c"]    # kappa > kappa_c -> sparse/decidable


def test_an_unreachable_coin_is_skipped_rather_than_cut():
    """"No balancing subset was found" is the absence of a measurement, not a measurement of zero
    ambiguity. The per-coin oracle spells it as negative infinity, and reading that as a low value
    cuts nearly every coin on the chain: 98.2% of input coins over a real 1,428-transaction slice."""
    from decluster.cost import amount_cuts
    def oracle(inputs, outputs):
        return {"coins": [{"role": "in", "index": 0, "value": 10, "log_w": float("-inf")},
                          {"role": "in", "index": 1, "value": 20, "log_w": None},
                          {"role": "in", "index": 2, "value": 30, "log_w": float("nan")},
                          {"role": "in", "index": 3, "value": 40, "log_w": 0.5}]}
    cuts = amount_cuts([10, 20, 30, 40], [95], oracle, count_oracle=_resolved())
    assert [c.index for c in cuts] == [3]        # only the coin that was actually measured


def test_the_per_coin_step_is_gated_on_the_whole_transaction_step():
    """The sequence is: classify the amounts, evaluate the transaction as a whole, then apportion
    across its coins. The third step running independently of the second is what let the per-coin
    oracle speak for transactions the transaction-level reading had found nothing in."""
    coins = [{"role": "in", "index": 0, "value": 100, "log_w": 0.0, "kappa_c": 0.9}]
    oracle = _fake_oracle(coins)
    calls = []

    def counting(inputs, outputs):
        calls.append((tuple(inputs), tuple(outputs)))
        return {"kind": "unknown", "count": None, "log_w": None}

    assert cost.amount_cuts([100, 200], [150, 150], oracle, count_oracle=counting) == []
    assert calls == [((100, 200), (150, 150))]      # the second step ran, and its verdict held


def test_the_link_matrix_oracle_reads_a_fee_paying_transaction():
    """The per-coin density oracle asks for an exact subset hit and goes quiet the moment a fee is
    paid. The link matrix reads the transaction's actual balance, so it still answers — and a row
    with one plausible output is a deterministic link, the amounts settling the assignment."""
    pytest.importorskip("dss")
    ins = [500_000, 300_000, 200_000]
    with_fee = [600_000, 395_000]                       # 5,000 sats of fee
    coins = cost.boltzmann_oracle(ins, with_fee)["coins"]
    assert [c["index"] for c in coins] == [0, 1, 2]
    assert all(c["log_w"] is not None for c in coins)
    assert cost.dss_oracle(ins, with_fee)["coins"]      # the other oracle runs, but goes quiet:
    assert all(c["log_w"] == float("-inf")
               for c in cost.dss_oracle(ins, with_fee)["coins"] if c["role"] == "in")

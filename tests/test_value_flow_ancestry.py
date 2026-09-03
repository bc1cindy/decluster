import pytest

from decluster import ancestry


def _coinbase(value):
    return {"vin": [{"is_coinbase": True}], "vout": [{"value": value}]}


def _input(txid, value):
    return {"txid": txid, "vout": 0, "prevout": {"value": value}}


def _fetch(transactions):
    return transactions.__getitem__


def test_value_flow_matrix_is_input_value_over_total_for_every_output():
    matrix = ancestry.value_flow_link_oracle([5, 3, 2], [3, 3, 2, 1])

    assert matrix == [
        pytest.approx([0.5, 0.5, 0.5, 0.5]),
        pytest.approx([0.3, 0.3, 0.3, 0.3]),
        pytest.approx([0.2, 0.2, 0.2, 0.2]),
    ]
    assert [sum(column) for column in zip(*matrix)] == pytest.approx([1.0] * 4)


def test_value_flow_refuses_zero_total_instead_of_inventing_a_transition():
    assert ancestry.value_flow_link_oracle([0, 0], [0]) is None


def test_value_flow_graph_does_not_call_subset_sum_oracle(monkeypatch):
    transactions = {
        "target": {
            "vin": [_input("small", 1), _input("large", 9)],
            "vout": [{"value": 10}],
        },
        "small": _coinbase(1),
        "large": _coinbase(9),
    }

    def fail_if_called(*args, **kwargs):
        raise AssertionError("the subset-sum oracle is not part of nominal-value flow")

    monkeypatch.setattr(ancestry, "dss_link_oracle", fail_if_called)
    graph = ancestry.build_value_flow_graph(
        ("target", 0), depth=2, fetch=_fetch(transactions)
    )

    assert ancestry.absorber_distribution(graph, ("target", 0)) == pytest.approx(
        {("small", 0): 0.1, ("large", 0): 0.9}
    )


def test_value_flow_absorption_matches_hand_calculated_two_hop_distribution():
    # target -> {A: 2/8, middle: 6/8}; middle -> {B: 2/6, D: 4/6}
    # Therefore the source distribution is A=1/4, B=1/4, D=1/2.
    transactions = {
        "target": {
            "vin": [_input("A", 2), _input("middle", 6)],
            "vout": [{"value": 8}],
        },
        "middle": {
            "vin": [_input("B", 2), _input("D", 4)],
            "vout": [{"value": 6}],
        },
        "A": _coinbase(2),
        "B": _coinbase(2),
        "D": _coinbase(4),
    }

    result = ancestry.value_flow_untraceability(
        ("target", 0), depth=3, fetch=_fetch(transactions)
    )

    assert result["distribution"] == pytest.approx(
        {("A", 0): 0.25, ("B", 0): 0.25, ("D", 0): 0.5}
    )
    assert result["untraceability"] == pytest.approx(1.5)
    assert result["n_absorbers"] == 3
    assert result["truncated"] == 0


def test_value_flow_is_output_independent_within_one_transaction():
    transactions = {
        "target": {
            "vin": [_input("A", 4), _input("B", 6)],
            "vout": [{"value": 1}, {"value": 9}],
        },
        "A": _coinbase(4),
        "B": _coinbase(6),
    }

    left = ancestry.value_flow_signature(
        ("target", 0), depth=2, fetch=_fetch(transactions)
    )
    right = ancestry.value_flow_signature(
        ("target", 1), depth=2, fetch=_fetch(transactions)
    )

    assert left == pytest.approx({("A", 0): 0.4, ("B", 0): 0.6})
    assert right == pytest.approx(left)

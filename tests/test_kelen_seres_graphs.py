"""Section 3 stationary and temporal account-graph contracts."""

import pytest

from decluster.baselines.kelen_seres_graphs import (
    Transfer,
    stationary_account_graph,
    temporal_account_graph,
)


def test_stationary_graph_aggregates_repeated_account_edges_and_ignores_time():
    transfers = [
        Transfer("later", "a", "b", 3, 2),
        Transfer("earlier", "a", "b", 2, 1),
    ]
    graph = stationary_account_graph(transfers, opening_balances={"a": 5})
    assert graph.edges == {("a", "b"): 5}
    assert graph.balances == {"a": 0, "b": 5}


def test_temporal_graph_splits_on_receipt_and_carries_previous_balance():
    transfers = [
        Transfer("receive-1", "source", "a", 10, 1),
        Transfer("spend", "a", "merchant", 4, 2),
        Transfer("receive-2", "other", "a", 3, 3),
    ]
    graph = temporal_account_graph(
        transfers, opening_balances={"source": 10, "other": 3, "a": 0, "merchant": 0}
    )
    assert graph.edges[("source", 0), ("a", 1)] == 10
    assert graph.edges[("a", 1), ("merchant", 1)] == 4
    assert graph.edges[("a", 1), ("a", 2)] == 6
    assert graph.edges[("other", 0), ("a", 2)] == 3
    # The old spend originates at a1. There is no forward edge from a2 back
    # into a1, so reversing the graph cannot trace it to receive-2.
    assert (("a", 2), ("a", 1)) not in graph.edges
    assert graph.balances["a"] == 9


def test_temporal_graph_refuses_to_invent_pre_window_balance():
    with pytest.raises(ValueError, match="insufficient"):
        temporal_account_graph(
            [Transfer("tx", "a", "b", 1, 0)], opening_balances={"a": 0, "b": 0}
        )


def test_temporal_self_transfer_conserves_instead_of_double_counting_balance():
    graph = temporal_account_graph(
        [Transfer("self", "a", "a", 4, 1)], opening_balances={"a": 10}
    )
    assert graph.edges == {(('a', 0), ('a', 1)): 10}
    assert graph.balances == {"a": 10}

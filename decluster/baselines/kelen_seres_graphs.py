"""Ledger-to-graph transformations from Kelen and Seres, Section 3.

The account transform requires explicit opening balances. This avoids deriving
private pre-window state from the observed transfers and mirrors the paper's
auxiliary-source treatment of initial balance.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Hashable, Iterable


Account = Hashable
Node = Hashable


@dataclass(frozen=True)
class Transfer:
    identifier: Hashable
    source: Account
    destination: Account
    amount: int
    timestamp: int


@dataclass(frozen=True)
class WeightedTransactionGraph:
    nodes: frozenset[Node]
    edges: dict[tuple[Node, Node], int]
    balances: dict[Account, int]


def _validated(transfers: Iterable[Transfer]):
    transfers = tuple(transfers)
    if any(isinstance(tx.amount, bool) or not isinstance(tx.amount, int) or tx.amount <= 0
           for tx in transfers):
        raise ValueError("transfer amounts must be positive integers")
    if len({tx.identifier for tx in transfers}) != len(transfers):
        raise ValueError("transfer identifiers must be unique")
    return transfers


def stationary_account_graph(transfers: Iterable[Transfer], *, opening_balances=None):
    """Aggregate transfers between stable account vertices, ignoring time."""

    transfers = _validated(transfers)
    balances = dict(opening_balances or {})
    edges = defaultdict(int)
    nodes = set(balances)
    for tx in transfers:
        nodes.update((tx.source, tx.destination))
        edges[(tx.source, tx.destination)] += tx.amount
        balances[tx.source] = balances.get(tx.source, 0) - tx.amount
        balances[tx.destination] = balances.get(tx.destination, 0) + tx.amount
    return WeightedTransactionGraph(frozenset(nodes), dict(edges), balances)


def temporal_account_graph(transfers: Iterable[Transfer], *, opening_balances):
    """Split an account whenever it receives, carrying its prior balance.

    Transfer order is ``(timestamp, repr(identifier))``. A payment leaves the
    sender's current snapshot and enters a newly created destination snapshot;
    the destination's preceding non-zero balance is carried to that snapshot.
    Consequently a reverse walk from an earlier payment cannot cross into a
    receipt that happened later.
    """

    transfers = _validated(transfers)
    balances = dict(opening_balances)
    accounts = set(balances)
    for tx in transfers:
        accounts.update((tx.source, tx.destination))
        balances.setdefault(tx.source, 0)
        balances.setdefault(tx.destination, 0)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in balances.values()):
        raise ValueError("opening balances must be non-negative integers")

    generation = {account: 0 for account in accounts}
    nodes = {(account, 0) for account in accounts}
    edges = defaultdict(int)
    for tx in sorted(transfers, key=lambda row: (row.timestamp, repr(row.identifier))):
        if balances[tx.source] < tx.amount:
            raise ValueError(f"insufficient opening/history balance for {tx.source!r}")
        source_node = (tx.source, generation[tx.source])
        previous_destination = (tx.destination, generation[tx.destination])
        balances[tx.source] -= tx.amount
        generation[tx.destination] += 1
        destination_node = (tx.destination, generation[tx.destination])
        nodes.add(destination_node)
        prior_balance = balances[tx.destination]
        if prior_balance:
            edges[(previous_destination, destination_node)] += prior_balance
        edges[(source_node, destination_node)] += tx.amount
        balances[tx.destination] += tx.amount
    return WeightedTransactionGraph(frozenset(nodes), dict(edges), balances)

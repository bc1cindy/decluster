"""Ledger-to-graph transformations from Kelen and Seres, Section 3.

Section 2.2 sets no restrictions on a node's incoming and outgoing amounts, and the
auxiliary source of Section 2.4 absorbs whatever a node spends without having received.
So the paper's model does not need opening balances, and `stationary_account_graph`
does not ask for them.

`temporal_account_graph` does, and the reason is local to that transform rather than
inherited from the paper: splitting an account into per-receipt snapshots makes each
snapshot hold a balance, and the carry edge into the next snapshot is only defined when
the spend does not exceed it. Requiring the balances up front also keeps pre-window state
from being back-derived out of the observed transfers.
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


@dataclass(frozen=True)
class AbsorbingTransactionChain:
    transient: tuple[Node, ...]
    absorbers: tuple[Node, ...]
    transitions: dict[Node, tuple[tuple[Node, float], ...]]


@dataclass(frozen=True)
class AuxiliarySource:
    node: Node


def absorbing_transaction_chain(graph: WeightedTransactionGraph):
    """Materialize Section 2.4 auxiliary sources and reversed transitions.

    For every node whose observed outgoing value exceeds its incoming value,
    an auxiliary predecessor supplies exactly that surplus. Reversing the
    augmented edges and normalizing by total incoming value implements
    Equation 1. Auxiliary nodes receive absorbing self-loops.
    """

    incoming = defaultdict(int)
    outgoing = defaultdict(int)
    predecessors = defaultdict(list)
    for (source, destination), amount in graph.edges.items():
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("graph edge weights must be positive integers")
        outgoing[source] += amount
        incoming[destination] += amount
        predecessors[destination].append((source, amount))

    absorbers = []
    for node in sorted(graph.nodes, key=repr):
        surplus = max(outgoing[node] - incoming[node], 0)
        if surplus:
            auxiliary = AuxiliarySource(node)
            absorbers.append(auxiliary)
            predecessors[node].append((auxiliary, surplus))
            incoming[node] += surplus

    transitions = {}
    for node in sorted(graph.nodes, key=repr):
        total = incoming[node]
        if total:
            transitions[node] = tuple(
                (previous, amount / total)
                for previous, amount in sorted(predecessors[node], key=lambda row: repr(row[0]))
            )
    for absorber in absorbers:
        transitions[absorber] = ((absorber, 1.0),)
    transient = tuple(sorted(graph.nodes, key=repr))
    return AbsorbingTransactionChain(transient, tuple(absorbers), transitions)


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

    `opening_balances` is required, and a snapshot spending more than it holds raises:
    the carry edge needs a non-negative remainder. This is a condition of the temporal
    split, not of the paper's graph model.
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

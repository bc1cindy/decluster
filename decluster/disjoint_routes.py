"""How many edge-disjoint routes join a coin to its candidate origins.

The framework states its two positive properties over this quantity and nothing else. Robust
connectivity asks that no small cut separate an output from the mass of its candidate origins —
that the two are joined by *multiple disjoint paths*. Own-origin robustness asks the same of the
paths back to a user's own antecedents. Both are the size of a minimum cut, and a minimum cut is
what a maximum flow measures.

`path_count` counts routes weighted by link probability, which is a different number: many routes
may share the same coin, so a large count says nothing about how few coins a cut would have to
sever. This module answers the cut question, and only that.

Two modelling choices, both the framework's rather than ours. Routes are **edge**-disjoint, which is
the reading the specification settled on: paths may pass through a shared transaction but may not
share a coin, because it is the coin that a seizure or a label removes. And several origins are
reduced to one by an artificial source joined to each, the standard construction, so `k` is the
number of routes to the origin *set* rather than to any particular member.

What this does not say. A flow treats value as fungible, and a transaction that mixes inputs does
not record which satoshi left by which output. A route here is a path the graph permits, not a claim
that particular value travelled it: `k` bounds how much redundancy a cut has to defeat, and any
reading beyond that is the taint-transfer question this module refuses to answer.

The quantity is the min cut of a directed graph with unit capacities, which is the connectivity
Abboud, Georgiadis, Italiano, Krauthgamer, Parotsidis, Trabelsi, Uznański and Wolleb-Graf study in
*Faster Algorithms for All-Pairs Bounded Min-Cuts* (arXiv:1807.05803). Two things there carry over.
The vertex-capacitated case reduces to the edge-capacitated one by splitting each vertex, which is
what puts a coin's single unit of capacity on an arc of its own here. And the useful question is
k-bounded: which coins have a *small* cut, rather than the exact value where it is large — on the
committed cache the whole finding sits at k = 1 and k = 2.

`catalog/ctp-sources.json` is the framework's own bibliography, pinned to its footnotes at a named
revision, so a method reference like this one does not belong in it and is cited here instead.
"""

from __future__ import annotations

from collections import deque

UNCAPPED = 1 << 30                     # a coin's own arc is the only scarce one
TARGET_VALUE = object()               # prune to what the target coin itself is worth
SOURCE = ("__source__", -1)
SINK = ("__sink__", -1)


class _Network:
    """A unit-capacity flow network over coins, held as an adjacency list of paired arcs."""

    def __init__(self):
        self.arcs = []                      # (head, capacity) with arcs[i ^ 1] the reverse
        self.out = {}

    def add(self, tail, head, capacity=1):
        self.out.setdefault(tail, []).append(len(self.arcs))
        self.arcs.append([head, capacity])
        self.out.setdefault(head, []).append(len(self.arcs))
        self.arcs.append([tail, 0])

    def _levels(self, source, sink):
        level = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for index in self.out.get(node, ()):
                head, capacity = self.arcs[index]
                if capacity > 0 and head not in level:
                    level[head] = level[node] + 1
                    queue.append(head)
        return level if sink in level else None

    def _augment(self, node, sink, level, cursor, limit):
        if node == sink:
            return limit
        arcs = self.out.get(node, ())
        while cursor[node] < len(arcs):
            index = arcs[cursor[node]]
            head, capacity = self.arcs[index]
            if capacity > 0 and level.get(head, -1) == level[node] + 1:
                pushed = self._augment(head, sink, level, cursor, min(limit, capacity))
                if pushed:
                    self.arcs[index][1] -= pushed
                    self.arcs[index ^ 1][1] += pushed
                    return pushed
            cursor[node] += 1
        return 0

    def max_flow(self, source, sink):
        """Dinic. Integral capacities in, integral flow out; with unit capacities that is `k`."""
        total = 0
        while (level := self._levels(source, sink)) is not None:
            cursor = {node: 0 for node in self.out}
            while (pushed := self._augment(source, sink, level, cursor, float("inf"))):
                total += pushed
        return total

    def saturated_routes(self, source, sink, carried):
        """One route per unit of flow, walked over arcs the flow used and not yet spent.

        `carried` reads the flow on a forward arc, which is what the reverse arc's capacity holds.
        A route is reported as the coins it passes through, in walk order.
        """
        remaining = {i: carried(i) for i in range(0, len(self.arcs), 2) if carried(i) > 0}
        routes = []
        while True:
            path, node = [], source
            while node != sink:
                step = next((i for i in self.out.get(node, ()) if remaining.get(i, 0) > 0), None)
                if step is None:
                    return routes
                remaining[step] -= 1
                node = self.arcs[step][0]
                path.append(node)
            routes.append([name for name, side in path[:-1] if side == "out"])

    def saturated_flow_routes(self, source, sink, carried):
        """Decompose an integral flow into ``(amount, route)`` records.

        Unlike ``saturated_routes``, this spends the bottleneck amount at once.  Calling the
        unit-flow decomposer for satoshi capacities would emit one route per satoshi even when
        every satoshi follows the same path.
        """
        remaining = {i: carried(i) for i in range(0, len(self.arcs), 2) if carried(i) > 0}
        routes = []
        while True:
            path, steps, node = [], [], source
            while node != sink:
                step = next((i for i in self.out.get(node, ()) if remaining.get(i, 0) > 0), None)
                if step is None:
                    return routes
                steps.append(step)
                node = self.arcs[step][0]
                path.append(node)
            amount = min(remaining[step] for step in steps)
            for step in steps:
                remaining[step] -= amount
            routes.append((amount, [name for name, side in path[:-1] if side == "out"]))


class _Restricted:
    """A view of `graph` holding only the coins in `keep`, so reachability is recomputed on them."""

    def __init__(self, graph, keep):
        self.edges = {coin: [(nxt, w) for nxt, w in graph.edges.get(coin, ()) if nxt in keep]
                      for coin in keep}


def _reachable_backwards(graph, target):
    """The coins a walk from `target` can still reach, so the cut is measured on live ground."""
    seen, queue = {target}, deque([target])
    while queue:
        coin = queue.popleft()
        for nxt, _weight in graph.edges.get(coin, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def route_capacity(graph, target, origins=None, carries=None):
    """`(k, routes)`: how many edge-disjoint routes join `target` to `origins`.

    `origins` defaults to the graph's absorbers — the boundary the walk stopped at. A coin that no
    longer reaches the target is dropped rather than counted as an origin it cannot serve.

    `carries` is the amount a route has to be able to deliver, in satoshis, and prunes every coin
    worth less than it before the cut is measured. Without it a route of a thousand satoshis counts
    the same as a route that could have supplied the whole coin, which overstates redundancy in the
    direction that matters: the specification prunes exactly this way — a path worth less than the
    amount in question may have been removed. `carries=TARGET_VALUE` uses the target's own value,
    the natural threshold for asking which routes could have produced it.
    """
    live = _reachable_backwards(graph, target)
    if carries is not None:
        floor = graph.values.get(target) if carries is TARGET_VALUE else carries
        if floor is not None:
            values = getattr(graph, "values", {})
            live = {coin for coin in live
                    if coin == target or (values.get(coin) or 0) >= floor}
            live = _reachable_backwards(_Restricted(graph, live), target)
    ends = [coin for coin in (origins if origins is not None else graph.absorbers)
            if coin in live and coin != target]
    if not ends:
        return 0, []

    # A coin is an edge, not a vertex: the specification puts transactions at the vertices and coins
    # on the arcs between them, because it is a coin that a seizure or a label removes. The graph
    # here keys state by coin, so each coin is split into an in/out pair joined by the one unit of
    # capacity it owns; a transition between coins is then uncapacitated. Max flow over that is the
    # number of coin-disjoint routes, and its min cut is the coins a separation would have to take.
    inward = lambda coin: (coin, "in")
    outward = lambda coin: (coin, "out")
    network = _Network()
    for coin in live:
        network.add(inward(coin), outward(coin), 1)
    for coin in live:
        for nxt, _weight in graph.edges.get(coin, ()):
            if nxt in live:
                network.add(outward(coin), inward(nxt), UNCAPPED)
    for end in ends:
        network.add(outward(end), SINK, UNCAPPED)
    # Every route leaves the target, so the target is the query point rather than a resource
    # routes compete for: the source joins its outward side, past its own unit of capacity.
    network.add(SOURCE, outward(target), UNCAPPED)

    k = network.max_flow(SOURCE, SINK)
    return k, network.saturated_routes(SOURCE, SINK, lambda i: network.arcs[i ^ 1][1])


def cut_size(graph, target, origins=None, carries=None):
    """The minimum number of coins whose removal separates `target` from every origin."""
    return route_capacity(graph, target, origins, carries)[0]

def flow_capacity(graph, target, origins=None):
    """`(satoshis, valued_routes)`: the largest value origins could deliver at once.

    The framework states its property over the *mass* of a coin's candidate origins, not only over
    how many routes reach it. Giving each coin its own value as capacity answers that: the maximum
    flow is the value the origin set could deliver if every route ran at once, and its minimum cut
    is the value a separation would have to remove.

    This is still one flow and still polynomial. What it is not is the k-splittable question —
    the most value carried by at most k routes — which is strongly NP-hard and is a choice about
    routing rather than a measurement of capacity.

    A coin whose value the walk did not record cannot bound anything, so it is treated as
    unconstrained rather than as zero: understating capacity here would invent a cut.
    """
    live = _reachable_backwards(graph, target)
    ends = [coin for coin in (origins if origins is not None else graph.absorbers)
            if coin in live and coin != target]
    if not ends:
        return 0, []
    values = getattr(graph, "values", {})
    worth = lambda coin: values.get(coin) or UNCAPPED
    inward, outward = lambda c: (c, "in"), lambda c: (c, "out")
    network = _Network()
    for coin in live:
        network.add(inward(coin), outward(coin), worth(coin))
    for coin in live:
        for nxt, _weight in graph.edges.get(coin, ()):
            if nxt in live:
                network.add(outward(coin), inward(nxt), UNCAPPED)
    for end in ends:
        network.add(outward(end), SINK, UNCAPPED)
    network.add(SOURCE, outward(target), UNCAPPED)
    total = network.max_flow(SOURCE, SINK)
    return total, network.saturated_flow_routes(SOURCE, SINK,
                                                lambda i: network.arcs[i ^ 1][1])

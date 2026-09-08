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
"""

from __future__ import annotations

from collections import deque

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

    def saturated_routes(self, source, sink):
        """One path per unit of flow, read off the arcs the flow saturated."""
        routes = []
        used = set()
        while True:
            path, node = [], source
            while node != sink:
                step = next((i for i in self.out.get(node, ())
                             if i % 2 == 0 and self.arcs[i][1] == 0 and i not in used), None)
                if step is None:
                    return routes
                used.add(step)
                node = self.arcs[step][0]
                path.append(node)
            routes.append([coin for coin in path if coin != sink])


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


def route_capacity(graph, target, origins=None):
    """`(k, routes)`: how many edge-disjoint routes join `target` to `origins`.

    `origins` defaults to the graph's absorbers — the boundary the walk stopped at. A coin that no
    longer reaches the target is dropped rather than counted as an origin it cannot serve.
    """
    live = _reachable_backwards(graph, target)
    ends = [coin for coin in (origins if origins is not None else graph.absorbers)
            if coin in live and coin != target]
    if not ends:
        return 0, []

    network = _Network()
    for coin in live:
        for nxt, _weight in graph.edges.get(coin, ()):
            if nxt in live:
                network.add(coin, nxt)
    for end in ends:
        network.add(end, SINK)
    network.add(SOURCE, target)

    k = network.max_flow(SOURCE, SINK)
    return k, network.saturated_routes(SOURCE, SINK)


def cut_size(graph, target, origins=None):
    """The minimum number of coins whose removal separates `target` from every origin."""
    return route_capacity(graph, target, origins)[0]

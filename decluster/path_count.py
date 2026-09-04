"""Probability-weighted provenance route accumulation over the ancestry DAG.

The module name is retained for compatibility. This is not a counterfactual k-routes algorithm:
it does not enumerate edge-disjoint paths or enforce plausible-flow capacity.

The origin distribution is weighted by link probability alone. Subset-sum multiplicity is NOT a
factor: `cost.py` declares the amount channel refuse-only — it may cut a coin from the graph, never
weight one — and multiplicity entering as a weight is what that forbids. Measured on a synthetic
two-origin DAG, the term moved min-entropy from 1.0 bit to 0.137; the direction is beside the point,
the objection is that an ambiguity signal was a weight at all. The combinatorial sub-transaction
literature reads a low mapping count as low privacy, so under that reading the weighting was the
correct ambiguity signal; the refuse-only contract overrides it, and this module does not pretend
the two agree.

Multiplicity, not redundancy: many routes may share the same coins, so this says nothing about how
few of them a cut would sever. Measuring that needs disjoint paths, which this repository does not
compute.
"""
import math

from .ancestry import build_extended_graph, _shannon, _min_entropy

NEG_INF = float("-inf")


def _logsumexp(a, b):
    if a == NEG_INF and b == NEG_INF:
        return NEG_INF
    m = a if a > b else b
    return m + math.log(math.exp(a - m) + math.exp(b - m))


def _topological_order(target, edges):
    """Kahn sort of the DAG `coin -> source` rooted at `target`, so a coin is always finalized
    before its sources consume its accumulated multiplicity. Every non-target node has >=1 inbound
    edge (it was only discovered by being someone's source), so `target` is the unique in-degree-0
    root."""
    indeg = {target: 0}
    for coin, srcs in edges.items():
        indeg.setdefault(coin, 0)
        for source, _w in srcs:
            indeg[source] = indeg.get(source, 0) + 1
    queue = [n for n, d in indeg.items() if d == 0]
    order = []
    while queue:
        n = queue.pop()
        order.append(n)
        for source, _w in edges.get(n, []):
            indeg[source] -= 1
            if indeg[source] == 0:
                queue.append(source)
    return order


def provenance_route_accumulation(
    target, *, depth=6, max_nodes=None, fetch=None, link_oracle=None, count_oracle=None
):
    """Provenance over ancestral origins, weighted by link probability alone. Reuses
    `build_extended_graph`'s walk (honoring `max_nodes` for deep-coinjoin tractability) -- does not
    re-walk. Returns {"origins_weighted": {origin: weight}, "min_entropy": float, "shannon": float,
    "truncated": int}.

    `link_oracle` default = `ancestry.value_flow_link_oracle`, the same walk `analyze`/`report`
    take; pass `oracle.bounded_dss_link_oracle()` for the opt-in subset-sum walk.

    `count_oracle` is accepted but unused: kept for backward compatibility with callers that still
    pass one. See the module docstring for why subset-sum multiplicity is not folded in here.

    Total mass to an origin sums, over every route from `target`, the product of edge link
    probabilities along it -- computed as a forward log-domain accumulation over the ancestry DAG
    (topological order; acyclic -> finite -> converges)."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    if link_oracle is None:
        from .ancestry import value_flow_link_oracle
        link_oracle = value_flow_link_oracle

    g = build_extended_graph(target, depth=depth, fetch=fetch, link_oracle=link_oracle,
                              max_nodes=max_nodes)

    log_reach = {target: 0.0}
    for coin in _topological_order(target, g.edges):
        edges_out = g.edges.get(coin)
        if not edges_out:
            continue  # absorber (incl. max_nodes truncation): no outgoing edges, never fetched
        base = log_reach.get(coin)
        if base is None:
            continue  # unreachable from target in this DAG (shouldn't occur; defensive)
        for source, w in edges_out:
            if w <= 0:
                continue
            log_reach[source] = _logsumexp(log_reach.get(source, NEG_INF),
                                           base + math.log(w))

    contrib = {o: log_reach[o] for o in g.absorbers if o in log_reach}
    if not contrib:
        return {"origins_weighted": {}, "min_entropy": 0.0, "shannon": 0.0,
                "truncated": g.truncated}

    total = contrib[next(iter(contrib))]
    for lr in list(contrib.values())[1:]:
        total = _logsumexp(total, lr)
    origins_weighted = {o: math.exp(lr - total) for o, lr in contrib.items()}

    probs = list(origins_weighted.values())
    return {"origins_weighted": origins_weighted, "min_entropy": _min_entropy(probs),
            "shannon": _shannon(probs), "truncated": g.truncated}


# Compatibility name. It predates the distinction between probability-weighted ancestry routes and
# the unimplemented CTP k-routes/edge-disjoint plausible-flow metric. New code should import
# `provenance_route_accumulation` from its canonical namespace.
path_count_anonymity = provenance_route_accumulation

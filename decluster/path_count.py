"""§07 path-count anonymity object: provenance over ancestral origins weighted by counterfactual
subset-sum PATH MULTIPLICITY, distinct from §04's set-size entropy
(`ancestry.absorber_distribution`, which weighs origins by link-probability mass alone). Reuses
`ancestry.build_extended_graph`'s walk verbatim (same graph, same `max_nodes` bound) and folds in
the dss W(E) mapping-count (`counting.w_total`) per edge: how many counterfactual subset-sum
routes reach each origin, not just how likely the single most-probable one is.

This is a LOWER BOUND / weight-of-evidence, never a privacy score -- exactly like every other
number in this module family."""
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


def path_count_anonymity(target, *, depth=6, max_nodes=None, fetch=None, link_oracle=None,
                          count_oracle=None):
    """§07 path-count anonymity set: provenance over ancestral origins weighted by counterfactual
    subset-sum PATH MULTIPLICITY, from the dss W(E) counts. This is the §07 path-like object (how
    many amount-consistent counterfactual routes reach each origin); it is NOT the §06 robustness
    metric, which is edge-disjoint path count / min-cut (k-routes max-flow) and is a separate,
    not-yet-implemented component — W(E) multiplicity and edge-disjoint connectivity are different
    quantities. Reuses
    `build_extended_graph`'s walk (honoring `max_nodes` for deep-coinjoin tractability) -- does not
    re-walk. Returns {"origins_weighted": {origin: weight}, "log_W_paths": float,
    "min_entropy": float, "shannon": float, "truncated": int}.

    Per-edge path multiplicity = link_prob * W(E) of the edge's tx (`g.edges` already stores
    link_prob as the row-stochastic `weight`; `coin.txid` names the tx that produced `coin`, whose
    W(E) scales every edge out of `coin`). Total multiplicity to an origin sums, over every route
    from `target`, the product of edge multiplicities along it -- computed as a forward log-domain
    accumulation over the ancestry DAG (topological order; acyclic -> finite -> converges).

    A LOWER BOUND / weight-of-evidence, not a privacy score. When a tx's W(E) is off-regime
    (`log_w` is None) that hop falls back to link-probability weight alone (multiplicity factor 1)
    -- never fabricate a count."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    if link_oracle is None:
        from .oracle import bounded_link_oracle
        link_oracle = bounded_link_oracle()
    if count_oracle is None:
        from .counting import w_total
        count_oracle = w_total

    g = build_extended_graph(target, depth=depth, fetch=fetch, link_oracle=link_oracle,
                              max_nodes=max_nodes)

    log_w_by_txid = {}

    def log_w_of(txid):
        if txid not in log_w_by_txid:
            tx = fetch(txid)
            in_vals = [v["prevout"]["value"] for v in tx["vin"]]
            out_vals = [o["value"] for o in tx["vout"]]
            res = count_oracle(in_vals, out_vals)
            lw = res.get("log_w")
            log_w_by_txid[txid] = 0.0 if lw is None else lw  # None -> link-prob-only fallback
        return log_w_by_txid[txid]

    log_reach = {target: 0.0}
    for coin in _topological_order(target, g.edges):
        edges_out = g.edges.get(coin)
        if not edges_out:
            continue  # absorber (incl. max_nodes truncation): no outgoing edges, never fetched
        base = log_reach.get(coin)
        if base is None:
            continue  # unreachable from target in this DAG (shouldn't occur; defensive)
        lw = log_w_of(coin[0])
        for source, w in edges_out:
            if w <= 0:
                continue
            log_edge = math.log(w) + lw
            log_reach[source] = _logsumexp(log_reach.get(source, NEG_INF), base + log_edge)

    contrib = {o: log_reach[o] for o in g.absorbers if o in log_reach}
    if not contrib:
        return {"origins_weighted": {}, "log_W_paths": NEG_INF,
                "min_entropy": 0.0, "shannon": 0.0, "truncated": g.truncated}

    log_w_paths = contrib[next(iter(contrib))]
    for lr in list(contrib.values())[1:]:
        log_w_paths = _logsumexp(log_w_paths, lr)
    origins_weighted = {o: math.exp(lr - log_w_paths) for o, lr in contrib.items()}

    probs = list(origins_weighted.values())
    return {"origins_weighted": origins_weighted, "log_W_paths": log_w_paths,
            "min_entropy": _min_entropy(probs), "shannon": _shannon(probs),
            "truncated": g.truncated}

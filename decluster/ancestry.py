"""Ancestry-entropy engine (exact absorber-model rung). A backward provenance walk over the tx
graph, weighted by the exact subset-sum link matrix, solved as an absorbing Markov chain. Every
number is a lower bound on the intrinsic graph entropy of the payment's provenance under no
auxiliary information — NOT a privacy score; subjectively discounted by the reader's threat model."""
import math


class Graph:
    """Backward provenance graph. Coins keyed by any hashable id (production: (txid, vout))."""
    def __init__(self):
        self.transient = []   # interior coins with backward link edges
        self.absorbers = []   # boundary coins: coinbase / depth-cutoff / oracle-None
        self.edges = {}       # coin -> [(next_coin, weight), ...], row-stochastic over next_coin
        self.truncated = 0    # count of coins made absorbers by the oracle-None refusal


def _solve(a, b):
    """Solve a @ x = b for x (a: n×n, b: n×m), partial-pivot Gaussian elimination. Pure Python;
    numpy is not a decluster dependency. Mutates local copies only."""
    n = len(a)
    m = len(b[0]) if b else 0
    aug = [list(a[i]) + list(b[i]) for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv][col]) < 1e-15:
            continue  # singular column; leave zeros (unreachable state)
        aug[col], aug[piv] = aug[piv], aug[col]
        pivot = aug[col][col]
        aug[col] = [v / pivot for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0.0:
                factor = aug[r][col]
                aug[r] = [aug[r][k] - factor * aug[col][k] for k in range(n + m)]
    return [row[n:] for row in aug]


def absorber_distribution(graph, target):
    """The target coin's absorption distribution over graph.absorbers: solve (I − Q) H = R and read
    the target's row. Returns {absorber: prob} for absorbers with positive mass."""
    if target in graph.absorbers:
        return {target: 1.0}
    t_index = {c: i for i, c in enumerate(graph.transient)}
    a_index = {c: i for i, c in enumerate(graph.absorbers)}
    nt, na = len(graph.transient), len(graph.absorbers)
    # I − Q  and  R
    im_q = [[1.0 if i == j else 0.0 for j in range(nt)] for i in range(nt)]
    r = [[0.0] * na for _ in range(nt)]
    for coin, i in t_index.items():
        for nxt, w in graph.edges.get(coin, []):
            if nxt in t_index:
                im_q[i][t_index[nxt]] -= w
            elif nxt in a_index:
                r[i][a_index[nxt]] += w
    h = _solve(im_q, r)                       # h[i][a] = P(absorb in a | start at transient i)
    row = h[t_index[target]]
    return {graph.absorbers[a]: p for a, p in enumerate(row) if p > 1e-12}


def _is_coinbase(tx):
    vin = tx.get("vin", [])
    return bool(vin) and vin[0].get("is_coinbase", False)


def build_extended_graph(target, depth=6, fetch=None, link_oracle=None):
    """Backward provenance walk from `target = (txid, vout)` to `depth` transactions. Each coin is a
    state keyed by (txid, vout); interior coins get backward link edges to their source coins,
    boundary coins (coinbase / depth-cutoff / oracle-None) become absorbers. Refuses to fabricate a
    link when the oracle returns None — truncates instead; truncation coarsens the absorber
    distribution (the en-route mass to the cut coin is invariant — only its onward spread collapses
    to an atom), which by the entropy grouping property (H_fine = H_coarse + Σ p·H(sub) ≥ H_coarse)
    cannot raise the entropy, and merging that mass into one atom cannot lower the max probability, so
    min-entropy cannot rise either — the safe direction for a lower bound on ambiguity (never
    overstating it). De-duplicates states by coin identity, so shared ancestors (diamonds) are exact.

    PROVISIONAL modelling choice (spec §9, not settled): edges are the row-stochastic normalisation
    of the link column (`col[i]/sum(col)`), weighting by LINK-PROBABILITY only. Why this is open:
    normalising the column this way can discard effective-value / fee-plausibility constraints (the
    upstream §05 caution — e.g. Wasabi-1 clustering information lives in the coins' effective values),
    and the theory's provenance measure is satoshi-weighted, not link-weighted. `L` already encodes
    the value multiset via subset-sum feasibility, but satoshi-flow value-weighting is deferred to the
    flow rung. `L` is uniform over non-derived mappings (the crate's definition), not
    multiplicity-weighted."""
    g = Graph()
    kind = {}                       # coin -> "transient" | "absorber"
    queue = [(target, depth)]       # BFS from target: first dequeue = largest remaining depth
    seen = set()
    while queue:
        coin, d = queue.pop(0)
        if coin in seen:
            continue
        seen.add(coin)
        txid, vout = coin
        tx = fetch(txid)
        if _is_coinbase(tx):
            kind[coin] = "absorber"; continue
        if d <= 0:
            kind[coin] = "absorber"; continue        # depth cutoff
        in_vals = [v["prevout"]["value"] for v in tx["vin"]]
        out_vals = [o["value"] for o in tx["vout"]]
        matrix = link_oracle(in_vals, out_vals)
        if matrix is None:
            kind[coin] = "absorber"; g.truncated += 1; continue   # refuse to fabricate
        col = [matrix[i][vout] for i in range(len(matrix))]
        s = sum(col)
        if s <= 0:
            kind[coin] = "absorber"; continue        # no link info -> boundary
        edges = []
        for i, v in enumerate(tx["vin"]):
            parent = (v["txid"], v["vout"])
            edges.append((parent, col[i] / s))
            queue.append((parent, d - 1))
        g.edges[coin] = edges
        kind[coin] = "transient"
    for coin, k in kind.items():
        (g.transient if k == "transient" else g.absorbers).append(coin)
    return g


def dss_link_oracle(inputs, outputs):
    """Default production link oracle: the exact subset-sum pairwise link matrix. Lazy import so
    decluster.ancestry loads without the compiled `dss` module (build: maturin develop)."""
    import dss
    return dss.pairwise_link_prob(list(inputs), list(outputs))


def _shannon(probs):
    return -sum(p * math.log2(p) for p in probs if p > 0)


def _min_entropy(probs):
    top = max(probs) if probs else 1.0
    return -math.log2(top) if top > 0 else 0.0


def ancestry_entropy(target, depth=6, fetch=None, link_oracle=dss_link_oracle):
    """Lower bound on the intrinsic graph entropy of the target coin's provenance under no auxiliary
    information — NOT a privacy score; subjectively discounted by the reader's threat model. Returns
    Shannon and min-entropy (the conservative, defender-side read) of the provenance distribution
    over the ancestral boundary, the boundary size, and how many coins were truncated (oracle-None)."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    g = build_extended_graph(target, depth=depth, fetch=fetch, link_oracle=link_oracle)
    dist = absorber_distribution(g, target)
    probs = list(dist.values())
    return {"shannon": _shannon(probs), "min_entropy": _min_entropy(probs),
            "n_absorbers": len(probs), "truncated": g.truncated}

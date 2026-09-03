"""Ancestry-entropy engines. A backward provenance walk over the tx
graph, solved as an absorbing Markov chain: the coin's
absorption distribution is the harmonic measure of the walk — the solution of the discrete Laplace
system (I − Q) H = R with absorbing boundary.

Two transition models are intentionally kept separate:

* ``build_value_flow_graph`` implements the nominal-value transition rule: an output walks back to
  every input of its creating transaction in proportion to that input's value.
* ``build_extended_graph`` is the experimental subset-sum-link model. It requires a link oracle and
  may additionally combine subjective evidence. It is not the nominal-value model.

Every number is a lower bound on the
intrinsic graph entropy of the payment's provenance under no auxiliary information — NOT a privacy
score; subjectively discounted by the reader's threat model."""
import math
from dataclasses import dataclass


class Graph:
    """Backward provenance graph. Coins keyed by any hashable id (production: (txid, vout))."""
    def __init__(self):
        self.transient = []   # interior coins with backward link edges
        self.absorbers = []   # boundary coins: coinbase / depth-cutoff / oracle-None
        self.edges = {}       # coin -> [(next_coin, weight), ...], row-stochastic over next_coin
        self.truncated = 0    # total: oracle-None refusals + max_nodes caps + any unnamed cause
        self.oracle_refused = 0        # the link oracle declined to link the coin's transaction
        self.node_capped = 0           # the max_nodes bound cut the frontier before any fetch
        self.zero_link_mass = 0        # the selected output has no positive incoming link mass
        self.unattributed = 0          # truncated by a cause this module does not name
        self.truncated_coins = {}      # coin -> cause, so truncation can be counted, and attributed,
                                       # over the mass-carrying boundary


ORACLE_REFUSED = "oracle_refused"
NODE_CAPPED = "node_capped"
ZERO_LINK_MASS = "zero_link_mass"


@dataclass(frozen=True)
class TruncationSupport:
    """How much of a signature's mass-carrying boundary is truncation, split by cause.

    The two causes answer different questions and a single total answers neither. `oracle_refused`
    is the link oracle declining to commit to a link; `node_capped` is the `max_nodes` bound cutting
    the frontier. A consumer reading "no view" off a total cannot tell which walk limit it hit, and
    under `value_flow_link_oracle` — which refuses only on zero total input value — the first is
    practically always zero, so a total silently means the second.

    `unattributed` holds truncation whose cause this module does not name. It stays in `total` —
    dropping it would under-report blindness — but it is never folded into one of the two names:
    a consumer that branches on a cause must not be handed one that was never measured.

    `zero_link_mass` is the third measured failure to continue: the selected output's link column
    has no positive mass.  It is kept separate from genuine boundaries such as coinbase and the
    requested depth cutoff.
    """

    oracle_refused: int
    node_capped: int
    unattributed: int = 0
    zero_link_mass: int = 0

    @property
    def total(self):
        return self.oracle_refused + self.node_capped + self.unattributed + self.zero_link_mass

    def __bool__(self):
        # Without this an all-zero support is truthy, so a caller's `if truncated:` — written
        # against the old bare int — would flip silently instead of failing where `>=` does.
        return self.total > 0


def _truncate(graph, kind, coin, cause):
    """Make `coin` a boundary absorber and record which walk limit put it there."""
    kind[coin] = "absorber"
    graph.truncated += 1
    graph.truncated_coins[coin] = cause
    if cause == ORACLE_REFUSED:
        graph.oracle_refused += 1
    elif cause == NODE_CAPPED:
        graph.node_capped += 1
    elif cause == ZERO_LINK_MASS:
        graph.zero_link_mass += 1
    else:
        graph.unattributed += 1


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


def build_extended_graph(target, depth=6, fetch=None, link_oracle=None, value_weighted=False,
                          subjective_oracle=None, max_nodes=None):
    """Backward provenance walk from `target = (txid, vout)` to `depth` transactions. Each coin is a
    state keyed by (txid, vout); interior coins get backward link edges to their source coins,
    boundary coins (coinbase / depth-cutoff / oracle-None) become absorbers. Refuses to fabricate a
    link when the oracle returns None — truncates instead; truncation coarsens the absorber
    distribution (the en-route mass to the cut coin is invariant — only its onward spread collapses
    to an atom), which by the entropy grouping property (H_fine = H_coarse + Σ p·H(sub) ≥ H_coarse)
    cannot raise the entropy, and merging that mass into one atom cannot lower the max probability, so
    min-entropy cannot rise either — the safe direction for a lower bound on ambiguity (never
    overstating it). De-duplicates states by coin identity, so shared ancestors (diamonds) are exact.

    `link_oracle` is required, and what it returns decides the transition model. The library's
    facades (`analyze`, `report`, `path_count_anonymity`, `ancestry_entropy`, `anonymity_set`) now
    pass `value_flow_link_oracle`; the paragraph below describes the subset-sum oracle, which is
    opt-in.

    PROVISIONAL modelling choice (spec §9, not settled) FOR THE SUBSET-SUM ORACLE: edges are the
    row-stochastic normalisation of the link column (`col[i]/sum(col)`), weighting by
    LINK-PROBABILITY only. Why this is open:
    normalising the column this way can discard effective-value / fee-plausibility constraints (the
    upstream §05 caution — e.g. Wasabi-1 clustering information lives in the coins' effective values),
    and the theory's provenance measure is satoshi-weighted, not link-weighted. `L` already encodes
    the value multiset via subset-sum feasibility, but satoshi-flow value-weighting is deferred to the
    flow rung. `L` is uniform over non-derived mappings (the crate's definition), not
    multiplicity-weighted.

    `value_weighted` (opt-in, default False) is an experimental hybrid: the link column is scaled by
    each input's satoshi value before normalising (`col[i]*in_val_i / Σ_k col[k]*in_val_k`). It is
    neither the plain subset-sum-link model nor the nominal-value transition model. Use
    `build_value_flow_graph` for the latter. The default stays link-probability-only so existing
    experimental results remain reproducible.

    `subjective_oracle` implements post-04's subjective matrix that combines with the graph-derived
    link matrix, applied at the link level before the absorbing solve (the §04-faithful fusion);
    default None keeps the graph-only walk.

    `max_nodes` (default None = no cap, reproduces prior behavior exactly) bounds the walk's cost
    to O(max_nodes) fetch/oracle calls regardless of depth -- the tractability lever for deep
    coinjoins, where exponential ancestor fan-out can otherwise hang. Once the graph has committed
    max_nodes coins (graph size = len(kind), the count already classified transient or absorber),
    every further dequeued coin is made a truncation absorber WITHOUT fetching or oracle-linking
    it, using the same boundary semantics as an oracle-None refusal (kind[coin]="absorber", counted
    in g.truncated and g.node_capped, its parents are never enqueued). BFS expands nearest coins
    first, so truncation falls on the deepest, least informative frontier, and the resulting
    absorber_distribution is a conservative LOWER BOUND: unexpanded ancestry is lumped into
    truncation, which can only add origins later, never remove. The bound is on fetch/oracle COST
    (<= max_nodes); the final coin count can exceed max_nodes by up to the one BFS frontier layer
    already queued when the cap trips (those extra coins are cheap no-fetch truncation absorbers).
    A coin that would have resolved to a genuine coinbase/depth-cutoff origin but is dequeued after
    the cap trips is folded into truncation instead — conservative (its mass becomes a truncation
    atom, never an invented origin)."""
    g = Graph()
    kind = {}                       # coin -> "transient" | "absorber"
    queue = [(target, depth)]       # BFS from target: first dequeue = largest remaining depth
    seen = set()
    while queue:
        coin, d = queue.pop(0)
        if coin in seen:
            continue
        seen.add(coin)
        if max_nodes is not None and len(kind) >= max_nodes:
            _truncate(g, kind, coin, NODE_CAPPED); continue   # node cap reached: truncate, no fetch
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
            _truncate(g, kind, coin, ORACLE_REFUSED); continue   # refuse to fabricate
        if subjective_oracle is not None:
            sub = subjective_oracle(tx, in_vals, out_vals)
            if sub is not None:
                matrix = [[matrix[i][j] * sub[i][j] for j in range(len(out_vals))]
                          for i in range(len(in_vals))]
        col = [matrix[i][vout] for i in range(len(matrix))]
        if value_weighted:
            col = [c * in_vals[i] for i, c in enumerate(col)]
        s = sum(col)
        if s <= 0:
            _truncate(g, kind, coin, ZERO_LINK_MASS); continue
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


def value_flow_link_oracle(inputs, outputs):
    """Return the collapsed nominal-value transition matrix.

    In the uncollapsed UTXO graph an output first walks to its creating transaction with
    probability one. From that transaction it walks to input ``i`` with probability
    ``inputs[i] / sum(inputs)``. Collapsing the deterministic output-to-transaction step yields the
    same column for every output. Output values and transaction fees therefore do not alter this
    transition rule.

    ``None`` is returned for a transaction with no positive input value, because no stochastic row
    can be constructed without inventing provenance.
    """
    total = sum(inputs)
    if total <= 0:
        return None
    probabilities = [value / total for value in inputs]
    return [[probability for _ in outputs] for probability in probabilities]


def build_value_flow_graph(target, depth=6, fetch=None, max_nodes=None):
    """Build the nominal-value absorbing walk over a UTXO ancestry graph.

    This is deliberately a separate entry point from the subset-sum-link experiment: it never
    imports or calls ``dss`` and has no amount-link or subjective-evidence weighting.
    """
    return build_extended_graph(
        target,
        depth=depth,
        fetch=fetch,
        link_oracle=value_flow_link_oracle,
        max_nodes=max_nodes,
    )


def value_flow_signature(target, depth=6, fetch=None, max_nodes=None):
    """Absorption probabilities produced by the nominal-value transition model."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    graph = build_value_flow_graph(target, depth=depth, fetch=fetch, max_nodes=max_nodes)
    return absorber_distribution(graph, target)


def value_flow_untraceability(target, depth=6, fetch=None, max_nodes=None):
    """Shannon untraceability and absorption details for the nominal-value model.

    ``untraceability`` is the Shannon entropy of the source absorption distribution in bits. The
    expected number of steps is not reported because transaction nodes are collapsed here; doing so
    would change the step-count observable even though it preserves absorption probabilities.
    """
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    graph = build_value_flow_graph(target, depth=depth, fetch=fetch, max_nodes=max_nodes)
    distribution = absorber_distribution(graph, target)
    probabilities = list(distribution.values())
    return {
        "untraceability": _shannon(probabilities),
        "distribution": distribution,
        "n_absorbers": len(probabilities),
        "truncated": graph.truncated,
    }


# Per-link wall-clock budget for the subset-sum oracle. Coin count is a poor cost predictor
# (same-size calls ranged 54ms-69s in dss's own measurements), so the walk truncates on time,
# admitting the cheap large mixes the old count guard refused and cutting only the genuine
# exponential blow-ups. Expiry is the same safe boundary as any other oracle-None refusal.
DEFAULT_LINK_BUDGET_MS = 2000


def dss_link_oracle(inputs, outputs, budget_ms=DEFAULT_LINK_BUDGET_MS):
    """Opt-in subset-sum link oracle; not any facade's default (see
    `ancestry.value_flow_link_oracle`). The exact subset-sum pairwise link matrix, bounded by a
    wall-clock budget so a dense mix truncates on time rather than on coin count. Lazy import so
    decluster.ancestry loads without the compiled `dss` module (build: maturin develop)."""
    import dss
    try:
        return dss.pairwise_link_prob(list(inputs), list(outputs), budget_ms)
    except BaseException:
        # dss can hard-panic (pyo3_runtime.PanicException, a BaseException, NOT an Exception) on
        # wide transactions; treat that the same as any other oracle refusal -> None (truncate).
        return None


def _shannon(probs):
    return -sum(p * math.log2(p) for p in probs if p > 0)


def _min_entropy(probs):
    top = max(probs) if probs else 1.0
    return -math.log2(top) if top > 0 else 0.0


def ancestry_signature(target, depth=6, fetch=None, link_oracle=value_flow_link_oracle):
    """The coin's **provenance signature**: its absorption distribution over ancestral boundary coins —
    a sparse, high-dimensional quasi-identifier vector (`{ancestor: mass}`). Same backward walk as
    `ancestry_entropy`, exposing the distribution instead of its entropy. This is the feature the
    deep-feature *matching* attack scores: two coins with overlapping signatures share provenance."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    g = build_extended_graph(target, depth=depth, fetch=fetch, link_oracle=link_oracle)
    return absorber_distribution(g, target)


def ancestry_signature_and_truncation(
    target, depth=6, fetch=None, link_oracle=value_flow_link_oracle
):
    """The signature, plus a `TruncationSupport` over the absorbers that carry its mass.

    Both come from one walk. The split is what makes an *empty* intersection readable: a boundary
    that is entirely truncation contains no observed origin, so two such signatures fail to overlap
    whatever their provenance is. Without it, "no shared origin" and "no view" are the same answer —
    and without the *cause*, "no view" does not say which limit produced it."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    g = build_extended_graph(target, depth=depth, fetch=fetch, link_oracle=link_oracle)
    sig = absorber_distribution(g, target)
    return sig, truncated_support(sig, g)


def truncated_support(signature, graph):
    """How many of a signature's *mass-carrying* absorbers are truncation, by cause.

    `graph.truncated` counts every truncated coin, including atoms this target never reaches with
    any mass. `absorber_distribution` reports only positive-mass absorbers, so comparing the two
    calls a branch blind while it is still resolving a full-mass origin. Consumers compare
    `TruncationSupport.total` against `len(signature)`, so both sides must count the same objects.
    A boundary coin the walk stopped at for a reason this module does not name is counted under
    `unattributed`.
    """
    causes = [graph.truncated_coins[a] for a in signature if a in graph.truncated_coins]
    # An unrecognised cause stays in the total, under `unattributed`, and is never given one of the
    # two names: under-reporting truncation lets an empty intersection be read as a refusal, and
    # naming an unmeasured cause lets a consumer act on a walk limit that never fired.
    return TruncationSupport(
        oracle_refused=sum(1 for c in causes if c == ORACLE_REFUSED),
        node_capped=sum(1 for c in causes if c == NODE_CAPPED),
        unattributed=sum(1 for c in causes
                         if c not in (ORACLE_REFUSED, NODE_CAPPED, ZERO_LINK_MASS)),
        zero_link_mass=sum(1 for c in causes if c == ZERO_LINK_MASS),
    )


def provenance_link(sig_a, sig_b, rarity=None):
    """Narayanan–Shmatikov quasi-identifier overlap of two provenance signatures: the shared ancestral
    coins, each scored by the mass it carries in *both* and, optionally, its global rarity
    `wt = 1/log2(support)` (a shared *rare* ancestor is strong same-origin evidence; a shared common
    one — a hub coinbase spent by everyone — is weak). `rarity` maps ancestor -> support count; absent,
    all shared ancestors weigh equally. Returns a non-negative link score (0 = disjoint provenance)."""
    shared = set(sig_a) & set(sig_b)
    if not shared:
        return 0.0
    def wt(c):
        if not rarity:
            return 1.0
        supp = rarity.get(c, 1)
        return 1.0 / math.log2(supp + 1) if supp > 1 else 1.0
    return sum(min(sig_a[c], sig_b[c]) * wt(c) for c in shared)


def ancestry_entropy(target, depth=6, fetch=None, link_oracle=value_flow_link_oracle):
    """Lower bound on the intrinsic graph entropy of the target coin's provenance under no auxiliary
    information — NOT a privacy score; subjectively discounted by the reader's threat model. Returns
    Shannon and min-entropy (the conservative, defender-side read) of the provenance distribution
    over the ancestral boundary, the boundary size, and how many coins were truncated. `truncated` is
    the total of both causes; `Graph.oracle_refused` and `Graph.node_capped` keep them apart."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    g = build_extended_graph(target, depth=depth, fetch=fetch, link_oracle=link_oracle)
    dist = absorber_distribution(g, target)
    probs = list(dist.values())
    return {"shannon": _shannon(probs), "min_entropy": _min_entropy(probs),
            "n_absorbers": len(probs), "truncated": g.truncated}

"""Intersect the candidate origins of coins a co-spend says are held together.

The attack this completes is the one the collaborative-transaction writeup calls
own-origin robustness, and it is multi-transaction by nature: each mix leaves a
coin with a *set* of plausible origins, and a later transaction spending two such
coins narrows both sets to their overlap. One mix output alone says nothing; two
that must share an owner say whatever their origins have in common.

Three pieces, and this module is only the third:

- `monitor.walk_frontier` supplies the occasion — a co-spend candidate. It does
  not decide that the co-spend is real; the mix threshold and the missing change
  identification are stated there.
- `ancestry.ancestry_signature` supplies each coin's origin set as
  `{ancestor: mass}` from a backward absorbing walk. `provenance.descended_inputs`
  is *not* a substitute: it tests direct parentage, one hop.
- Here the sets are intersected across the branches.

What comes out is a *narrowing*, never an attribution: the shared origins are what
survives if the co-spend is genuine. Whether it is genuine is `cluster_refined`'s
question, which scores fingerprint and topology alongside the co-spend prior and
can refuse it. Passing this result off as ownership skips exactly the step that
distinguishes an intersection attack from the common-input heuristic.
"""

import math


def rarity_weight(ancestor, rarity):
    """N-S quasi-identifier weight `1/log2(support+1)`; 1.0 when support is unknown.

    A shared *rare* origin is strong evidence of a common source; a hub every
    wallet touches is nearly worthless. Matches `ancestry.provenance_link`.
    """
    if not rarity:
        return 1.0
    support = rarity.get(ancestor, 1)
    return 1.0 / math.log2(support + 1) if support > 1 else 1.0


def cluster_key(ancestor, cluster_of):
    """The wallet an origin coin belongs to, or the coin itself when it is unclustered.

    Both forms fall back to the coin. A callable that answers `None` for a coin it does not
    know would otherwise collapse every unclustered origin onto one shared pseudo-cluster, and
    branches with nothing in common would intersect at full mass — a fabricated attribution,
    which is the one failure this module must not have.
    """
    c = cluster_of(ancestor) if callable(cluster_of) else cluster_of.get(ancestor, ancestor)
    return ancestor if c is None else c


def shared_origins(signatures, rarity=None, cluster_of=None, cluster_rarity=None):
    """Ancestors present in *every* signature, with the mass all of them carry.

    `signatures` is a list of `{ancestor: mass}`. Returns
    `[(ancestor, mass, weight)]`, heaviest weighted mass first. Mass is the
    minimum across branches — an origin explains the co-spend only as far as its
    weakest branch supports it.

    Empty covers two different states and does not distinguish them: the
    branches genuinely share no origin, or some branch has no known origins at
    all. Only the first refuses the reading that they came from one place; read
    `sizes` from [`evaluate`] to tell them apart.
    """
    if not signatures:
        return []
    if cluster_of is not None:
        # Cluster-lift (the writeup's "the candidate origins are not coins, but rather
        # clusters", under Robust connectivity, cit-42): coarsen each coin-origin to its
        # owning cluster, summing masses, and intersect WALLETS rather than coins.
        def _lift(sig):
            out = {}
            for a, m in sig.items():
                c = cluster_key(a, cluster_of)
                out[c] = out.get(c, 0) + m
            return out
        signatures = [_lift(s) for s in signatures]
        if rarity is not None and cluster_rarity is None:
            raise ValueError("cluster_rarity is required when weighting cluster-lifted origins")
        # Cluster support must be measured over the population, not reconstructed from only the
        # branches in this intersection. Reusing coin support or local branch counts biases hubs.
        rarity = cluster_rarity
    common = set(signatures[0])
    for sig in signatures[1:]:
        common &= set(sig)
        if not common:
            return []
    out = [
        (a, min(s[a] for s in signatures), rarity_weight(a, rarity)) for a in common
    ]
    out.sort(key=lambda r: -(r[1] * r[2]))
    return out


def collapse_bits(smallest, n_shared):
    """How far the intersection narrowed the origin set, in bits.

    `log2(before / after)`, which is the currency the rest of the repository
    reports in — `subtransaction.ambiguity_bits`, `cluster.counterparty_bits`,
    `ancestry_entropy`. A raw difference of origins is not comparable across
    branches of different sizes; bits are.

    `None` when there is nothing to measure: no signature at all, or an empty
    intersection. An empty intersection is a refusal — the branches share no
    origin — not an unbounded narrowing, and reporting it as infinite bits would
    turn the strongest refusal into the strongest claim.
    """
    if smallest <= 0 or n_shared <= 0:
        return None
    return math.log2(smallest / n_shared)


def accumulate_intersections(observations, rarity=None, cluster_of=None, universe_size=None,
                             cluster_rarity=None):
    """Cross-event accumulation. Each observation is a list of branch signatures (one co-spend /
    linkage event); intersecting the surviving origin set across successive linked observations is
    where the compounding comes from — the writeup's "O(log n) observations, each cutting the
    candidate set by a constant factor" (Robust connectivity). The rate is Danezis and Serjantov's
    statistical-disclosure result, not Goldfeder's: the intersection paper demonstrates the attack
    but states no shrink law. `universe_size`, when known, includes the first observation's
    narrowing in `total_bits`; without it the returned bits are explicitly relative to the first
    observed candidate set. Returns (survivors, total_bits)."""
    surviving = None
    total = 0.0
    for sigs in observations:
        step = {a for a, _, _ in shared_origins(sigs, rarity, cluster_of, cluster_rarity)}
        if surviving is None:
            surviving = step
            if universe_size is not None and step:
                first = collapse_bits(universe_size, len(step))
                if first:
                    total += first
            continue
        before = len(surviving)
        surviving = surviving & step
        b = collapse_bits(before, len(surviving)) if surviving else None
        if b:
            total += b
    return (surviving or set()), total


def score_candidate(candidate, cluster_fn, funder_of, signatures=None):
    """Hand a co-spend candidate to the engine and report what it decided.

    `cluster_fn(nodes, signatures)` runs `cluster.cluster_refined` over the
    relevant nodes and returns its `(groups, refused, linked)`. `signatures` maps
    an outpoint to its `{ancestor: mass}` and is re-keyed here by funder, because
    the engine partitions transactions while the walk tracks coins; pass None to
    leave the engine's provenance channel dark rather than fed a guess. `funder_of` maps an outpoint to the
    txid that created it, since the engine partitions transactions. The co-spend
    itself is added to those nodes: the engine reads edges out of a node's inputs,
    so without it the pair under test does not exist as far as the engine knows.

    Returns `{"believed", "refused_pairs", "groups"}`. `believed` is True only
    when every branch's funder landed in one group and no pair of them appears in
    `refused` — that is, the engine fused the co-spend prior with fingerprint,
    amount and topology and still kept them together. False means the engine
    refused a merge the co-spend alone would have made, which is the case the
    whole partition-refinement design exists for.

    This is the step that separates an intersection attack from the common-input
    heuristic: the co-spend is an input to the decision, not the decision.
    """
    funders = [funder_of(op) for op in candidate.get("outpoints", [])]
    # The engine derives a co-spend edge by walking each node's inputs, so the
    # spending transaction has to be in the node set. Passing the funders alone
    # hands it nothing to score and every verdict comes back refused.
    nodes = list(dict.fromkeys(funders + [candidate.get("txid")]))
    by_node = None
    if signatures is not None:
        by_node = {funder_of(op): sig for op, sig in signatures.items()}
    groups, refused, _linked = cluster_fn([n for n in nodes if n is not None], by_node)
    wanted = set(funders)
    together = any(wanted <= set(g) for g in groups)
    # cluster_refined reports a refusal as (a, b, channel, ...); only the pair
    # is read here, so the rest of the shape stays the engine's business.
    refused_pairs = [r for r in refused if {r[0], r[1]} <= wanted]
    return {
        "believed": bool(together and not refused_pairs),
        "refused_pairs": refused_pairs,
        "groups": groups,
    }


def _truncation_causes(reported):
    """One branch's truncation as `(total, causes)`.

    Accepts an `ancestry.TruncationSupport` — the walk limits kept apart — or a bare integer total.
    A bare total names no cause and is reported with `causes=None` rather than being assigned to
    one; guessing here is what made `blind` unreadable in the first place. Anything else raises:
    coercing, say, a float count would round a caller's measurement without telling them.
    """
    oracle = getattr(reported, "oracle_refused", None)
    capped = getattr(reported, "node_capped", None)
    if oracle is None or capped is None:
        if isinstance(reported, bool) or not isinstance(reported, int):
            raise TypeError("truncation_of must return an int total or an ancestry.TruncationSupport, "
                            f"not {type(reported).__name__}")
        return reported, None
    unattributed = getattr(reported, "unattributed", 0)
    zero_link_mass = getattr(reported, "zero_link_mass", 0)
    return oracle + capped + unattributed + zero_link_mass, {
        "oracle_refused": oracle, "node_capped": capped,
        "zero_link_mass": zero_link_mass, "unattributed": unattributed,
    }


def _blind_cause(truncated, causes, sizes):
    """Which walk limit blinded the blind branches: a cause name, `"mixed"`, `"unknown"` or None.

    `unknown` is a real answer, not a missing one: it says at least one blind branch's cause was
    never measured — the caller reported a bare total, or a cause this tree does not name. It
    DOMINATES: an unmeasured cause alongside a measured one is still unknown, never `"mixed"`,
    because `"mixed"` asserts that both named walk limits fired and one of them was never observed.

    `None` means no blind branch had anything to attribute: every one of them is blind with zero
    truncation, which is a branch that observed nothing at all rather than one a walk limit cut.
    `evaluate` also returns `None` when nothing is blind; `blind` tells the two apart.
    """
    names = set()
    for total, cause, size in zip(truncated, causes, sizes):
        if total < size or total == 0:
            continue
        if cause is None:
            names.add("unknown")
            continue
        names |= {name for name, count in cause.items() if count}
    if "unknown" in names or "unattributed" in names:
        return "unknown"
    if not names:
        return None
    return names.pop() if len(names) == 1 else "mixed"


def evaluate(candidate, signature_of, rarity=None, truncation_of=None,
             cluster_of=None, cluster_rarity=None):
    """Intersect the origin sets of the coins one co-spend candidate consumes.

    `candidate` is an entry from `monitor.walk_frontier`'s `candidates`.
    `signature_of` maps an outpoint to its `{ancestor: mass}` signature — in
    production `ancestry.ancestry_signature`, in tests whatever is injected.

    Returns `{"txid", "branches", "sizes", "shared", "collapsed",
    "collapsed_bits", "scored"}`. `collapsed` is the number of origins the
    intersection removed relative to the smallest branch, and `collapsed_bits`
    the same narrowing as `log2(before/after)` — the attack's whole yield, zero
    when the co-spend tells us nothing new. Both are reported because the count
    says how many origins went and the bits say how much that was worth against
    branches of different sizes.

    `truncation_of`, when supplied, maps an outpoint to how much of its boundary is truncation
    rather than an origin, and adds `truncated`, `truncated_causes`, `blind` and `blind_cause`.
    `blind` is True when some branch's boundary is *entirely* truncation: that branch contributes no
    observed origin, so an empty `shared` says the walk could not see, not that the branches came
    from different places. Reading a blind empty as a refusal is the failure mode this field exists
    to prevent. The count must be over the absorbers that carry mass —
    `ancestry.ancestry_signature_and_truncation` reports it that way — since comparing every
    truncated coin against only the positive-mass boundary calls a branch blind while it is still
    resolving a full-mass origin.

    A branch is blinded by one of two different walk limits, and `blind` alone does not say which.
    Pass `ancestry.TruncationSupport` and `truncated_causes` carries the split per branch, with
    `blind_cause` naming what blinded the blind ones:

    - `"oracle_refused"` — the link oracle declined to link.
    - `"node_capped"` — the `max_nodes` bound cut the frontier.
    - `"zero_link_mass"` — the selected output had no positive incoming link mass.
    - `"mixed"` — more than one measured cause fired across the blind branches.
    - `"unknown"` — at least one blind branch's cause was not measured: a bare integer total, or a
      cause this tree does not name (`TruncationSupport.unattributed`). It dominates the named
      values, so `"mixed"` never covers for a cause nobody observed.
    - `None` — with `blind` False, nothing was blind, including when `truncation_of` was not
      supplied at all. With `blind` **True**, a branch is blind with zero truncation: it observed
      no origins and no walk limit cut it, so there is no cause to name. `blind` is what separates
      those two `None`s, and a consumer asking "why is this blind" must read it first.

    Under `ancestry.value_flow_link_oracle` — which refuses only on zero total input value — the
    oracle-refusal half is practically always zero, so a default-oracle walk that comes back blind
    was blinded by `max_nodes`, and now says so rather than leaving the reader to infer it.

    `cluster_of` lifts each origin to its owning wallet before intersecting, which is what the
    writeup asks for: the candidate origins are clusters, not coins, so two branches can overlap
    without their origin coins being connected on the transaction graph, and the clusters being
    intersected are the pre-mix ones where privacy is weakest. `sizes` and the narrowing are then
    reported over wallets. Weighting a lifted intersection needs `cluster_rarity` measured over the
    population (`propagate.build_cluster_rarity`); coin support does not survive the coarsening.

    `scored` is always False. The narrowing is conditional on the co-spend being
    genuine, and deciding that is [`score_candidate`], which runs the engine over
    the branches' funders and can refuse a merge the co-spend alone would have
    made. Reporting this result without that step asserts the common-input
    heuristic under the attack's name.
    """
    outpoints = list(candidate.get("outpoints", []))
    signatures = [signature_of(op) for op in outpoints]
    if cluster_of is not None:
        # Report sizes in the same objects the intersection runs over, or `collapsed` compares
        # a wallet count against a coin count and reads as a narrowing that never happened.
        sizes = [len({cluster_key(a, cluster_of) for a in s}) for s in signatures]
    else:
        sizes = [len(s) for s in signatures]
    shared = shared_origins(signatures, rarity, cluster_of, cluster_rarity)
    smallest = min(sizes) if sizes else 0
    reported = ([_truncation_causes(truncation_of(op)) for op in outpoints]
                if truncation_of else None)
    truncated = [total for total, _ in reported] if reported else None
    causes = [cause for _, cause in reported] if reported else None
    blind = bool(truncated) and any(t >= n for t, n in zip(truncated, sizes))
    return {
        "txid": candidate.get("txid"),
        "branches": len(outpoints),
        "sizes": sizes,
        "truncated": truncated,
        "truncated_causes": causes,
        "blind": blind,
        "blind_cause": _blind_cause(truncated, causes, sizes) if blind else None,
        "shared": shared,
        "collapsed": max(0, smallest - len(shared)),
        "collapsed_bits": collapse_bits(smallest, len(shared)),
        "scored": False,
    }

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


def shared_origins(signatures, rarity=None):
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


def evaluate(candidate, signature_of, rarity=None, truncation_of=None):
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

    `truncation_of`, when supplied, maps an outpoint to how many of its absorbers are the link
    oracle refusing rather than an origin, and adds `truncated` and `blind`. `blind` is True when
    some branch's boundary is *entirely* truncation: that branch contributes no observed origin, so
    an empty `shared` says the walk could not see, not that the branches came from different places.
    Reading a blind empty as a refusal is the failure mode this field exists to prevent.

    `scored` is always False. The narrowing is conditional on the co-spend being
    genuine, and deciding that is [`score_candidate`], which runs the engine over
    the branches' funders and can refuse a merge the co-spend alone would have
    made. Reporting this result without that step asserts the common-input
    heuristic under the attack's name.
    """
    outpoints = list(candidate.get("outpoints", []))
    signatures = [signature_of(op) for op in outpoints]
    sizes = [len(s) for s in signatures]
    shared = shared_origins(signatures, rarity)
    smallest = min(sizes) if sizes else 0
    truncated = [truncation_of(op) for op in outpoints] if truncation_of else None
    return {
        "txid": candidate.get("txid"),
        "branches": len(outpoints),
        "sizes": sizes,
        "truncated": truncated,
        "blind": bool(truncated) and any(t >= n for t, n in zip(truncated, sizes)),
        "shared": shared,
        "collapsed": max(0, smallest - len(shared)),
        "collapsed_bits": collapse_bits(smallest, len(shared)),
        "scored": False,
    }

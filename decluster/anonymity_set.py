"""M1 provenance anonymity set (Object A) — the §04 entropic anonymity set of a coin. The graph-
derived provenance distribution over ancestral origins (ancestry.absorber_distribution) is
multiplicatively reweighted by subjective knowledge (post 04's "subjective matrix combines with the
graph-derived one"); subjective evidence NARROWS which origins are plausible, so the min-entropy
(the conservative anonymity-set size — a lower bound / weight-of-evidence, not a privacy score)
decays. The per-coin object of the tx-graph anonymity-set theory; the M3 partition posterior is its
same-owner-clustering dual. Offline, stdlib only."""
from .ancestry import _min_entropy, _shannon

_EPS = 1e-12


def anonymity_bits(dist):
    """min-entropy (conservative, defender-side) and Shannon entropy of a provenance distribution."""
    probs = list(dist.values())
    return {"min_entropy": _min_entropy(probs), "shannon": _shannon(probs)}


def reweight(dist, factors):
    """Multiplicative subjective reweighting: P'(o) ∝ dist(o)·factors.get(o, 1.0), renormalized.
    All-1.0 factors is a no-op; an indicator collapses to a point mass (confidence-1 evidence)."""
    w = {o: max(dist[o], 0.0) * max(factors.get(o, 1.0), 0.0) for o in dist}
    tot = sum(w.values())
    if tot <= _EPS:
        n = len(dist)
        return {o: 1.0 / n for o in dist} if n else {}
    return {o: w[o] / tot for o in dist}


def provenance_anonymity(target, hypotheses, *, depth=6, fetch=None, link_oracle=None,
                          base_dist=None):
    """Reweighted provenance distribution for `target`: the graph-derived absorption distribution
    (ancestry), multiplicatively narrowed by each subjective hypothesis (name, factors)."""
    if base_dist is None:
        from .ancestry import build_extended_graph, absorber_distribution, dss_link_oracle
        if fetch is None:
            from .fetch import fetch_tx
            fetch = fetch_tx
        g = build_extended_graph(target, depth=depth, fetch=fetch,
                                  link_oracle=link_oracle or dss_link_oracle)
        base_dist = absorber_distribution(g, target)
    dist = dict(base_dist)
    for _name, factors in hypotheses:
        dist = reweight(dist, factors)
    return dist


def decay(base_dist, hypotheses):
    """min-entropy after each hypothesis is folded in, starting from the graph-only base. Monotone
    non-increasing for narrowing hypotheses (evidence ruling origins out)."""
    dist = dict(base_dist)
    trace = [("graph", anonymity_bits(dist)["min_entropy"])]
    for name, factors in hypotheses:
        dist = reweight(dist, factors)
        trace.append((name, anonymity_bits(dist)["min_entropy"]))
    return trace


def provenance_overlap_hypothesis(reference_sig, origins, *, sig_of, rarity=None,
                                   name="provenance", suppress=1e-6):
    """A narrowing hypothesis: origins whose provenance signature overlaps the reference keep full
    weight; non-overlapping origins are suppressed. `sig_of` maps origin -> its provenance signature."""
    from .ancestry import provenance_link
    factors = {}
    for o in origins:
        w = provenance_link(reference_sig, sig_of.get(o, {}), rarity)
        factors[o] = 1.0 if w > 0.0 else suppress
    return (name, factors)


def provenance_anonymity_fused(target, subjective_oracle, *, depth=6, fetch=None, link_oracle=None,
                                value_weighted=False):
    """§04-faithful provenance anonymity set: the absorption distribution of the backward walk whose
    per-tx link matrices are combined with the subjective matrix BEFORE solving (subjective_oracle
    folded into build_extended_graph). A concentrating subjective oracle sharpens the distribution
    (lower entropy) by routing mass through same-owner links — the link-level fusion the post-solve
    `reweight` cannot do. `value_weighted` (default False, backward-compatible) passes through to
    build_extended_graph's Gap C satoshi-flow weighting."""
    from .ancestry import build_extended_graph, absorber_distribution, dss_link_oracle
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    g = build_extended_graph(target, depth=depth, fetch=fetch,
                             link_oracle=link_oracle or dss_link_oracle,
                             value_weighted=value_weighted,
                             subjective_oracle=subjective_oracle)
    return absorber_distribution(g, target)


def sameowner_link_oracle(same_owner_pairs, boost=9.0):
    """A concrete §04 subjective oracle: `same_owner_pairs(tx) -> set of (input_i, output_j)` believed
    same-owner (from change-ID / demix / fingerprint); boosts those link-matrix entries by `boost`,
    leaves others at 1.0, abstains (None) when the set is empty."""
    def oracle(tx, in_vals, out_vals):
        pairs = same_owner_pairs(tx)
        if not pairs:
            return None
        m = [[1.0] * len(out_vals) for _ in in_vals]
        for (i, j) in pairs:
            if 0 <= i < len(in_vals) and 0 <= j < len(out_vals):
                m[i][j] = boost
        return m
    return oracle


def change_id_pairs(tx):
    """CIOH + change-ID: the change output is same-owner as every input. {(i, change_index)}.
    A CLUSTERING signal (same-owner as the input cluster), uniform over inputs: boosting every
    (i, change_index) pair equally cancels on the per-tx provenance column's renormalization, so it
    does not sharpen a single tx's per-tx provenance link column (see subjective_same_owner_pairs).
    It would feed a cluster-level analysis, not this walk — not a default source here."""
    from .extractors import _change_index
    c = _change_index(tx)
    if c is None:
        return set()
    return {(i, c) for i in range(len(tx.get("vin", [])))}


def address_reuse_pairs(tx):
    """Address-reuse self-transfer: an input whose prevout address reappears as an output address is
    same-owner with that output."""
    ins = tx.get("vin", [])
    outs = tx.get("vout", [])
    pairs = set()
    for i, v in enumerate(ins):
        ia = v.get("prevout", {}).get("scriptpubkey_address")
        if not ia:
            continue
        for j, o in enumerate(outs):
            if o.get("scriptpubkey_address") == ia:
                pairs.add((i, j))
    return pairs


def demix_pairs(tx):
    """Best-effort coinjoin demix: a uniquely-matched input and its participant's change output are
    same-owner. coinjoin_demix returns {input_index: participant_id} where participant_id is the
    matched CHANGE VALUE, not an output index — so we look up the output index whose value equals
    that change value (the demix's uniqueness guarantee means at most one such output)."""
    from .coinjoin_demix import coinjoin_demix
    in_vals = [v.get("prevout", {}).get("value") for v in tx.get("vin", [])]
    out_vals = [o.get("value") for o in tx.get("vout", [])]
    if not in_vals or not out_vals or any(v is None for v in in_vals + out_vals):
        return set()
    matched = coinjoin_demix(in_vals, out_vals)   # {input_index: change_value}
    pairs = set()
    for i, change_value in matched.items():
        hits = [j for j, v in enumerate(out_vals) if v == change_value]
        if len(hits) == 1:      # only pin when the change value is unique to one output;
            pairs.add((i, hits[0]))   # a duplicated value could belong to any owner — don't guess
    return pairs


def cluster_of_from_groups(groups):
    """{member: cluster_id} flatten of a list of member lists. Members must already be the objects
    `cluster_pairs` looks up — i.e. ADDRESSES. `cluster_refined` groups funding TXIDS, not
    addresses, so its output must go through `cluster_of_from_tx_groups` (below), not this."""
    return {addr: cid for cid, g in enumerate(groups) for addr in g}


def cluster_of_from_tx_groups(groups, fetch):
    """{address: cluster_id} from `cluster_refined`'s TXID groups. Each same-owner group of funding
    txids contributes every INPUT prevout address of every tx in the group, all sharing that group's
    id: co-spend clustering is common-INPUT ownership, so the input addresses are the entity's.
    Output addresses are deliberately NOT blanket-assigned — an output is same-owner only when it is
    change/self-transfer, which `cluster_pairs` still recovers whenever that output address recurs as
    an input elsewhere in the same cluster. Bridges `cluster_refined` (clusters txids) to
    `cluster_pairs` (needs an address->owner map); `fetch` is txid -> tx dict."""
    cluster_of = {}
    for cid, g in enumerate(groups):
        for txid in g:
            for v in fetch(txid).get("vin", []):
                a = v.get("prevout", {}).get("scriptpubkey_address")
                if a:   # falsy (None or "") == absent, matching cluster_pairs / address_reuse_pairs
                    cluster_of[a] = cid
    return cluster_of


def cluster_pairs(tx, cluster_of):
    """§04 subjective source from a same-owner clustering: (input_i, output_j) when input i's prevout
    address and output j's address are in the same cluster. Used as a closure over `cluster_of`."""
    ins = tx.get("vin", [])
    outs = tx.get("vout", [])
    pairs = set()
    for i, v in enumerate(ins):
        ia = v.get("prevout", {}).get("scriptpubkey_address")
        ci = cluster_of.get(ia) if ia else None
        if ci is None:
            continue
        for j, o in enumerate(outs):
            oa = o.get("scriptpubkey_address")
            if oa is not None and cluster_of.get(oa) == ci:
                pairs.add((i, j))
    return pairs


def subjective_oracle_for(cluster_of=None):
    """The §04 subjective link oracle from the default detectors: address-reuse self-transfer, plus
    (when `cluster_of` is given) the same-owner clustering source. Shared by report.report and
    analyze()."""
    if cluster_of is not None:
        srcs = (address_reuse_pairs, lambda t: cluster_pairs(t, cluster_of))
        pairs_fn = lambda t: subjective_same_owner_pairs(t, sources=srcs)
    else:
        pairs_fn = subjective_same_owner_pairs
    return sameowner_link_oracle(pairs_fn)


def subjective_same_owner_pairs(tx, sources=None):
    """The §04 'additional analysis' adapter: union of same-owner (input_i, output_j) beliefs from the
    detector sources, assembled into per-tx subjective link pairs. Feed to sameowner_link_oracle.
    Default source is address_reuse_pairs only: it differentiates inputs on the per-tx provenance
    column. change_id_pairs is deliberately excluded from the default — it boosts every input equally
    toward the change output, which cancels on renormalization and is inert here (see its docstring);
    it is a cluster-level signal, callers doing cluster-level analysis can pass it explicitly."""
    if sources is None:
        sources = (address_reuse_pairs,)
    pairs = set()
    for src in sources:
        pairs |= src(tx)
    return pairs

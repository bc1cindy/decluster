"""Public entry point: fused provenance anonymity-set analysis of a transaction's outputs, §04 of
tx-graph-anonymity-sets. Thin orchestration over the tested walk/fusion stack (ancestry +
anonymity_set) — NO new science. This is the facade an external consumer (e.g. wasabi-model) imports
to get per-coin provenance anonymity sets robustly at any depth (default 5): an oracle refusal (or,
on the opt-in subset-sum oracle, a dss panic) on a tx it cannot handle truncates that branch
(ancestry's existing None-boundary) rather than raising, and never fabricates a link. The default
walk is `ancestry.value_flow_link_oracle`, which takes no dss and refuses only a transaction with no
positive input value. (Errors outside the oracle — a failing `fetch`, a malformed tx
dict, an out-of-range target — still propagate; wrap the call if the caller must survive those.)"""
from . import cluster as _cluster_mod
from .ancestry import build_extended_graph, absorber_distribution
from .anonymity_set import anonymity_bits, cluster_of_from_tx_groups, provenance_anonymity_fused, \
    subjective_oracle_for
from .rarity_weight_baseline import Combiner
from .partition_model import build_evidence, contract_cospend
from .provenance_route_accumulation import provenance_route_accumulation
from .report import _spendable_vouts
from .split_merge import M3_MAX_SUPERNODES, m3_gap_and_samples


def analyze(tx, targets=None, depth=5, *, fetch=None, link_oracle=None,
            value_weighted=False, cluster_of=None, subjective=True, with_origins=True,
            max_nodes=None, path_count=False):
    """Public entry point: fused provenance anonymity-set analysis of a transaction's outputs (§04
    of tx-graph-anonymity-sets). Thin orchestration over the tested walk/fusion stack — NO new
    science. Robust at any depth (default 5): an oracle refusal or dss panic on a tx it cannot handle
    truncates that branch (counted in `truncated`, per ancestry's existing None-boundary) rather than
    raising. Errors outside the oracle (a failing `fetch`, a malformed tx dict, an out-of-range
    target) still propagate — wrap the call if the caller must survive those.

    tx: a txid str (fetched via `fetch`) OR a tx dict (offline). targets: vout indices (default all
    spendable outputs). link_oracle default = ancestry.value_flow_link_oracle (nominal-value
    transitions; no dss). The subset-sum walk is opt-in: pass
    `oracle.bounded_dss_link_oracle(budget_ms)` explicitly. Both facades of this walk (`analyze`
    and `report`) take the same default, so they read one walk two ways. value_weighted = Gap C satoshi-flow weighting. cluster_of = {address: owner} folded
    into the §04 subjective source. with_origins includes the absorber distribution per target.
    max_nodes (default None = uncapped, backward-compatible) is the deep-coinjoin tractability knob:
    bounds both walks' cost to O(max_nodes) fetch/oracle calls regardless of depth (a lower bound on
    the coin's ambiguity, never an overstatement — see build_extended_graph). path_count (default
    False, backward-compatible) exposes the provenance-route diagnostic under its legacy response
    name. It reuses the same link-probability-only walk as §04; no W(E)/subset-sum count is folded in.
    It is not the §07 robust-connectivity object: it does not enumerate edge-disjoint paths, impose
    plausible-flow capacity or implement k-routes.

    Returns {vout: {
        "provenance": {"min_entropy", "shannon", "n_absorbers", ["origins": {ancestor: mass}]},
        ["fused": {"min_entropy", "shannon"}],   # when subjective
        ["path_count": {"min_entropy", "shannon", "origins_weighted"}],  # compatibility key
        "truncated": int,   # the provenance (graph) walk's truncation count (oracle-None + max_nodes);
                            # the fused/path_count walks cap identically under the same max_nodes.
    }}. `provenance.min_entropy` is a conservative lower bound on the coin's provenance ENTROPY under no
    auxiliary information (§04); §06 reads such entropy as a lower bound on the graph cuts to
    de-anonymize, but that transfer is NOT adopted for this absorber-model entropy (see PAPER §10) — the
    number is an entropy bound, not a cut count. `fused` is clamped to <= provenance (subjective evidence
    never widens the set)."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    if link_oracle is None:
        from .ancestry import value_flow_link_oracle
        link_oracle = value_flow_link_oracle
    if isinstance(tx, str):
        tx = fetch(tx)
    txid = tx["txid"]
    vouts = targets if targets is not None else _spendable_vouts(tx)

    out = {}
    for vout in vouts:
        g = build_extended_graph((txid, vout), depth=depth, fetch=fetch, link_oracle=link_oracle,
                                  value_weighted=value_weighted, max_nodes=max_nodes)
        dist = absorber_distribution(g, (txid, vout))
        gb = anonymity_bits(dist)
        provenance = {"min_entropy": gb["min_entropy"], "shannon": gb["shannon"],
                      "n_absorbers": len(dist)}
        if with_origins:
            provenance["origins"] = dist
        entry = {"provenance": provenance, "truncated": g.truncated}
        if subjective:
            sub_oracle = subjective_oracle_for(cluster_of)
            fdist = provenance_anonymity_fused((txid, vout), sub_oracle, depth=depth, fetch=fetch,
                                                link_oracle=link_oracle, value_weighted=value_weighted,
                                                max_nodes=max_nodes)
            fb = anonymity_bits(fdist)
            entry["fused"] = {"min_entropy": min(fb["min_entropy"], provenance["min_entropy"]),
                              "shannon": min(fb["shannon"], provenance["shannon"])}
        if path_count:
            pc = provenance_route_accumulation(
                (txid, vout),
                depth=depth,
                max_nodes=max_nodes,
                fetch=fetch,
                link_oracle=link_oracle,
            )
            entry["path_count"] = {k: pc[k] for k in
                                    ("min_entropy", "shannon", "origins_weighted")}
        out[vout] = entry
    return out


def cluster_map(txids, fetch=None):
    """{address: owner_id} for a set of transactions — the same-owner clustering (cluster_refined,
    the fingerprint-aware engine) bridged to the address→owner map that analyze(cluster_of=...) folds
    into the §04 subjective source. `fetch` (txid -> tx dict) defaults to decluster.fetch.fetch_tx and
    is bound as cluster_refined's fetch dependency for the call."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    orig_fetch_tx = _cluster_mod.fetch_tx
    _cluster_mod.fetch_tx = fetch
    try:
        groups, _refused, _linked = _cluster_mod.cluster_refined(list(txids), Combiner.from_library())
    finally:
        _cluster_mod.fetch_tx = orig_fetch_tx
    return cluster_of_from_tx_groups(groups, fetch)


def cluster_posterior(txs, seed=0):
    """M3 — the exact-Bayesian partition posterior over the co-spend super-nodes of `txs` (a list of
    tx dicts). A same-owner CHECK, not the headline. Returns {"n_supernodes": int,
    "worst_partition_gap": float, "coassignment": {(i, j): P_same_partition}}: the worst per-partition
    gap between the split-merge sampler's stationary distribution and exact enumeration (the exactness
    gate), and the sampler's per-super-node-pair posterior P(same partition)."""
    cospend_groups = contract_cospend(txs)[:M3_MAX_SUPERNODES]
    supernodes = [{"txs": [txs[i] for i in g], "sig": {}} for g in cospend_groups]
    ev = build_evidence(supernodes)
    gap, samples = m3_gap_and_samples(ev, seed)
    coassignment = {}
    if ev.n >= 2 and samples:
        n = len(samples)
        for i in range(ev.n):
            for j in range(i + 1, ev.n):
                coassignment[(i, j)] = sum(1 for s in samples if s[i] == s[j]) / n
    return {"n_supernodes": ev.n, "worst_partition_gap": gap, "coassignment": coassignment}

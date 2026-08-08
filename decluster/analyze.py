"""Public entry point: fused provenance anonymity-set analysis of a transaction's outputs, §04 of
tx-graph-anonymity-sets. Thin orchestration over the tested walk/fusion stack (ancestry +
anonymity_set) — NO new science. This is the facade an external consumer (e.g. wasabi-model) imports
to get per-coin provenance anonymity sets robustly at any depth (default 5): an oracle refusal or dss
panic on a tx it cannot handle truncates that branch (ancestry's existing None-boundary) rather than
raising, and never fabricates a link. (Errors outside the oracle — a failing `fetch`, a malformed tx
dict, an out-of-range target — still propagate; wrap the call if the caller must survive those.)"""
from . import cluster as _cluster_mod
from .ancestry import build_extended_graph, absorber_distribution
from .anonymity_set import anonymity_bits, cluster_of_from_tx_groups, provenance_anonymity_fused, \
    subjective_oracle_for
from .combiner import Combiner
from .partition_model import build_evidence, contract_cospend
from .report import _spendable_vouts
from .split_merge import M3_MAX_SUPERNODES, m3_gap_and_samples


def analyze(tx, targets=None, depth=5, *, fetch=None, link_oracle=None,
            value_weighted=False, cluster_of=None, subjective=True, with_origins=True):
    """Public entry point: fused provenance anonymity-set analysis of a transaction's outputs (§04
    of tx-graph-anonymity-sets). Thin orchestration over the tested walk/fusion stack — NO new
    science. Robust at any depth (default 5): an oracle refusal or dss panic on a tx it cannot handle
    truncates that branch (counted in `truncated`, per ancestry's existing None-boundary) rather than
    raising. Errors outside the oracle (a failing `fetch`, a malformed tx dict, an out-of-range
    target) still propagate — wrap the call if the caller must survive those.

    tx: a txid str (fetched via `fetch`) OR a tx dict (offline). targets: vout indices (default all
    spendable outputs). link_oracle default = oracle.bounded_link_oracle() (panic-safe, resolves
    coinjoins). value_weighted = Gap C satoshi-flow weighting. cluster_of = {address: owner} folded
    into the §04 subjective source. with_origins includes the absorber distribution per target.

    Returns {vout: {
        "provenance": {"min_entropy", "shannon", "n_absorbers", ["origins": {ancestor: mass}]},
        ["fused": {"min_entropy", "shannon"}],   # when subjective
        "truncated": int,
    }}. `provenance.min_entropy` is the §06 lower bound on the graph cuts to de-anonymize the coin;
    `fused` is clamped to <= provenance (subjective evidence never widens the set)."""
    if fetch is None:
        from .fetch import fetch_tx
        fetch = fetch_tx
    if link_oracle is None:
        from .oracle import bounded_link_oracle
        link_oracle = bounded_link_oracle()
    if isinstance(tx, str):
        tx = fetch(tx)
    txid = tx["txid"]
    vouts = targets if targets is not None else _spendable_vouts(tx)

    out = {}
    for vout in vouts:
        g = build_extended_graph((txid, vout), depth=depth, fetch=fetch, link_oracle=link_oracle,
                                  value_weighted=value_weighted)
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
                                                link_oracle=link_oracle, value_weighted=value_weighted)
            fb = anonymity_bits(fdist)
            entry["fused"] = {"min_entropy": min(fb["min_entropy"], provenance["min_entropy"]),
                              "shannon": min(fb["shannon"], provenance["shannon"])}
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

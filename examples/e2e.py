"""Tier-1 offline end-to-end pipeline validation, plus Tier-2 LIVE end-to-end (`run_live`).
Composes the tested pieces of the pipeline — cluster.cluster_refined (Layer 4),
anonymity_set.cluster_of_from_tx_groups (Task 1), report.report (the §04 fused readout), and the M3
split-merge/enumerate exactness gate (partition_model + split_merge) — over ONE slice, and asserts
the plumbing invariants hold end to end. No new science: every term is an existing tested
function; this module only wires them together. `run_offline` sources the slice offline/
deterministically; `run_live` sources it from mempool.space via a real, bounded live fetch
(network + subprocess; see its own docstring) — the live-only imports it needs are deferred
inside the function body so the offline path (and the offline test suite) never touches them.
"""
from collections import Counter

from decluster import cluster as cluster_mod
from decluster.anonymity_set import cluster_of_from_tx_groups
from decluster.combiner import Combiner
from decluster.partition_model import build_evidence, contract_cospend
from decluster.report import report as fused_report
from decluster.split_merge import sample as sm_sample, enumerate_posterior

M3_MAX_SUPERNODES = 5


def _partition_key(labels, n):
    return tuple(sorted(tuple(sorted(k for k in range(n) if labels[k] == c))
                        for c in set(labels)))


def _m3_gap_and_samples(ev, seed):
    """Worst per-partition gap between the split-merge sampler's stationary distribution and
    exact enumeration (test_split_merge.py::test_sample_stationary_matches_enumeration's pattern),
    plus the raw post-burn label samples (reused by `run_live` for co-assignment agreement).
    ev.n == 0 has no partitions to compare; treat as an exact match with no samples."""
    if ev.n == 0:
        return 0.0, []
    out = sm_sample(ev, n_iter=4000, burn=1000, seed=seed)
    exact = {tuple(sorted(part)): p for part, p in enumerate_posterior(ev)}
    counts = Counter(_partition_key(s, ev.n) for s in out["labels_samples"])
    tot = sum(counts.values()) or 1
    emp = {k: v / tot for k, v in counts.items()}
    keys = set(exact) | set(emp)
    gap = max(abs(exact.get(k, 0.0) - emp.get(k, 0.0)) for k in keys)
    return gap, out["labels_samples"]


def _m3_worst_partition_gap(ev, seed):
    return _m3_gap_and_samples(ev, seed)[0]


def _first_input_address(tx):
    """First non-empty prevout address among a tx's inputs — the representative address used to
    place an M3 super-node in `cluster_of` (mirrors partition_model.contract_cospend's own choice
    of `addrs[0]` as the union-find root for a tx)."""
    for v in tx.get("vin", []):
        a = v.get("prevout", {}).get("scriptpubkey_address")
        if a:
            return a
    return None


def _m3_coassignment_agreement(ev, samples, cluster_of, supernode_addrs, threshold=0.5):
    """Fraction of M3 super-node pairs (i, j) where the split-merge sampler's posterior P(same
    partition) — the fraction of post-burn samples with labels[i] == labels[j] — agrees (on the
    `threshold` side) with whether cluster_refined placed their representative addresses in the
    same cluster. A cross-check between the exact-Bayesian partition posterior (M3) and the
    production clustering engine (Layer 4), not an identity: they use different evidence, so
    disagreement is informative, not necessarily a bug. None when there are fewer than 2
    super-nodes or no samples to estimate the posterior from."""
    if ev.n < 2 or not samples:
        return None
    n = len(samples)
    agree = total = 0
    for i in range(ev.n):
        for j in range(i + 1, ev.n):
            m3_same = (sum(1 for s in samples if s[i] == s[j]) / n) > threshold
            ai, aj = supernode_addrs[i], supernode_addrs[j]
            cluster_same = (ai is not None and aj is not None
                             and cluster_of.get(ai) is not None
                             and cluster_of.get(ai) == cluster_of.get(aj))
            agree += (m3_same == cluster_same)
            total += 1
    return agree / total


def run_offline(sample, targets, fetch, link_oracle, seed=0):
    """Run the full pipeline over a deterministic, offline slice.

    sample: list of tx dicts (the slice).
    targets: list of (txid, vout) pairs to report on.
    fetch: txid -> tx dict (offline, deterministic; also bound as cluster_refined's fetch_tx
        dependency for the duration of the clustering call — Layer 4 has no fetch parameter of
        its own, see decluster/cluster.py).
    link_oracle: (in_vals, out_vals) -> link matrix, offline/deterministic.
    seed: RNG seed for the M3 split-merge sampler.

    Returns {"report_targets": {(txid, vout): report entry}, "m3_worst_partition_gap": float,
    "m3_n_supernodes": int, "n_clusters": int, "cluster_groups": [[node, ...], ...],
    "n_cluster_nodes": int, "cluster_of": {address: cluster_id}}. `cluster_of` is the exact map the
    pipeline fed to the §04 source (exposed so a test can assert the wiring is address-keyed, not the
    txid-keyed map the bridge exists to prevent).
    """
    # 1. cluster_refined (Layer 4): the co-spend-aware engine. `sample` is tx dicts; cluster_refined
    # takes node identifiers it fetches itself, so nodes = the slice's own txids.
    nodes = [tx["txid"] for tx in sample]
    orig_fetch_tx = cluster_mod.fetch_tx
    cluster_mod.fetch_tx = fetch
    try:
        groups, _refused, _linked = cluster_mod.cluster_refined(nodes, Combiner.from_library())
    finally:
        cluster_mod.fetch_tx = orig_fetch_tx
    cluster_of = cluster_of_from_tx_groups(groups, fetch)

    # 2. report.report per target: fused (subjective) vs graph-only min-entropy.
    report_targets = {}
    for txid, vout in targets:
        rep = fused_report(fetch(txid), cluster_of=cluster_of, subjective=True, fetch=fetch,
                           link_oracle=link_oracle, oracle=lambda i, o: {"coins": []},
                           targets=[vout], depth=2)
        report_targets[(txid, vout)] = rep["targets"][vout]

    # 3. M3: co-spend super-nodes for the slice -> Evidence -> sampler vs exact enumeration.
    cospend_groups = contract_cospend(sample)[:M3_MAX_SUPERNODES]
    supernodes = [{"txs": [sample[i] for i in g], "sig": {}} for g in cospend_groups]
    ev = build_evidence(supernodes)
    m3_gap = _m3_worst_partition_gap(ev, seed)

    return {"report_targets": report_targets, "m3_worst_partition_gap": m3_gap,
            "m3_n_supernodes": ev.n, "n_clusters": len(groups), "cluster_groups": groups,
            "n_cluster_nodes": len(nodes), "cluster_of": cluster_of}


def run_live(max_targets=5, cap_total=120, wall_ms=6000, depth=2, seed=0):
    """Tier-2 LIVE end-to-end: the SAME pipeline as `run_offline` (cluster_refined -> cluster_of ->
    fused report per target -> M3 split-merge vs exact enumeration), but sourced from a real,
    live-fetched slice instead of a fixture/cache slice.

    Sourcing: `decluster.fetch.fetch_tx` (mempool.space, on-disk cached to `.cache/` so a repeated
    txid is not re-fetched) supplies both the tx dicts and cluster_refined's fetch dependency.
    Candidate txids come from `examples.anonymity_set_scale.seed_targets()` — real multi-input,
    non-coinjoin-scale txids drawn from the local tx history — reusing that module's seed/slice
    approach rather than inventing a new one. The link oracle is
    `examples.anonymity_set.hard_bounded_link_oracle`: a subprocess, wall-clock-killed dss call
    (see that module's docstring — the native subset-sum oracle can hang past its own cooperative
    `budget_ms` on dense mixes), so a coinjoin-heavy ancestor truncates the walk instead of hanging
    the run. `cap_total` bounds the slice used for both cluster_refined and the M3 super-nodes;
    `max_targets` bounds how many of that slice's txs get a full report() walk (the wall-clock cost
    driver). All are hard-bounded — this function is meant to run in minutes, not deterministically
    reproduce a fixed answer (real chain data, real timing-bounded oracle truncation).

    Live-only imports (decluster.fetch, examples.anonymity_set, examples.anonymity_set_scale) are
    deferred to inside this function so the offline import path — and the offline test suite —
    never touches the network.

    Returns the same shape as `run_offline`, plus:
      "n_targets_attempted": len(targets actually walked).
      "n_targets_resolved": coinjoin-ancestry resolution count — targets whose graph-only walk
        completed with zero oracle-refusal truncations (`ancestry_entropy`'s own `truncated`
        count, 0 meaning fully resolved).
      "m3_coassignment_agreement": see `_m3_coassignment_agreement`; None if the live slice didn't
        yield >= 2 M3 super-nodes.
    Returns {"error": ...} instead if no live candidate resolved at all (e.g. network unavailable).
    """
    import functools

    from decluster.fetch import fetch_tx as fetch
    from examples.anonymity_set import hard_bounded_link_oracle
    from examples.anonymity_set_scale import seed_targets

    link_oracle = functools.partial(hard_bounded_link_oracle, wall_ms=wall_ms)

    sample = []
    for txid in seed_targets():
        if len(sample) >= cap_total:
            break
        try:
            tx = fetch(txid)
        except Exception:
            continue
        if tx.get("vin") and tx.get("vout"):
            sample.append(tx)
    if not sample:
        return {"error": "no live candidates resolved (network/API unavailable)"}

    targets = [(tx["txid"], 0) for tx in sample[:max_targets]]

    # 1. cluster_refined (Layer 4), over the live slice — same call as run_offline, live fetch bound.
    nodes = [tx["txid"] for tx in sample]
    orig_fetch_tx = cluster_mod.fetch_tx
    cluster_mod.fetch_tx = fetch
    try:
        groups, _refused, _linked = cluster_mod.cluster_refined(nodes, Combiner.from_library())
    finally:
        cluster_mod.fetch_tx = orig_fetch_tx
    cluster_of = cluster_of_from_tx_groups(groups, fetch)

    # 2. report.report per target: fused (subjective) vs graph-only min-entropy, live ancestry.
    report_targets = {}
    n_resolved = 0
    for txid, vout in targets:
        rep = fused_report(fetch(txid), cluster_of=cluster_of, subjective=True, fetch=fetch,
                           link_oracle=link_oracle, oracle=lambda i, o: {"coins": []},
                           targets=[vout], depth=depth)
        entry = rep["targets"][vout]
        report_targets[(txid, vout)] = entry
        if not entry["truncated"]:
            n_resolved += 1

    # 3. M3: co-spend super-nodes for the slice -> Evidence -> sampler vs exact enumeration, plus
    # the sampler's co-assignment posterior cross-checked against cluster_refined's own grouping.
    cospend_groups = contract_cospend(sample)[:M3_MAX_SUPERNODES]
    supernodes = [{"txs": [sample[i] for i in g], "sig": {}} for g in cospend_groups]
    supernode_addrs = [_first_input_address(sn["txs"][0]) for sn in supernodes]
    ev = build_evidence(supernodes)
    m3_gap, m3_samples = _m3_gap_and_samples(ev, seed)
    m3_agreement = _m3_coassignment_agreement(ev, m3_samples, cluster_of, supernode_addrs)

    return {"report_targets": report_targets, "m3_worst_partition_gap": m3_gap,
            "m3_n_supernodes": ev.n, "m3_coassignment_agreement": m3_agreement,
            "n_clusters": len(groups), "cluster_groups": groups, "n_cluster_nodes": len(nodes),
            "n_targets_attempted": len(targets), "n_targets_resolved": n_resolved}


def _run_live_cli(argv):
    """`--live [max_targets] [cap_total] [wall_ms] [depth]` — Tier-2 live run. Network + subprocess
    (see run_live's docstring for the bounds). Defaults are chosen so the run actually RESOLVES
    real coinjoin ancestry rather than truncating it: the exact subset-sum oracle needs ~2.3s on a
    dense payment+mix, so `wall_ms` defaults to 6000 (a 1500ms bound refuses those to a point mass);
    `depth=2` keeps the bounded-oracle fan-out to minutes. This entry is `__main__`-guarded on
    purpose — `hard_bounded_link_oracle` spawns worker processes (macOS spawn re-imports the entry
    module), so an unguarded caller makes every oracle call fail-closed to None (truncate)."""
    max_targets = int(argv[0]) if len(argv) > 0 else 5
    cap_total = int(argv[1]) if len(argv) > 1 else 20
    wall_ms = int(argv[2]) if len(argv) > 2 else 6000
    depth = int(argv[3]) if len(argv) > 3 else 2
    out = run_live(max_targets=max_targets, cap_total=cap_total, wall_ms=wall_ms, depth=depth)
    if "error" in out:
        return out
    return {
        "n_targets_attempted": out["n_targets_attempted"],
        "n_targets_resolved": out["n_targets_resolved"],
        "n_clusters": out["n_clusters"],
        "n_cluster_nodes": out["n_cluster_nodes"],
        "m3_worst_partition_gap": out["m3_worst_partition_gap"],
        "m3_n_supernodes": out["m3_n_supernodes"],
        "m3_coassignment_agreement": out["m3_coassignment_agreement"],
        "targets": {f"{txid}:{vout}": {"min_entropy": t["min_entropy"],
                                       "fused_min_entropy": t.get("fused_min_entropy"),
                                       "truncated": t["truncated"]}
                   for (txid, vout), t in out["report_targets"].items()},
    }


if __name__ == "__main__":
    import json
    import sys

    if "--live" in sys.argv:
        summary = _run_live_cli([a for a in sys.argv[1:] if a != "--live"])
        print(json.dumps(summary, indent=2))
    else:
        import functools

        from examples.ns_propagation_cache_run import build_sample, cache_fetch_tx, load_cache_txs
        from decluster.ancestry import dss_link_oracle

        all_txs = load_cache_txs()
        node_ids, *_ = build_sample(all_txs, cap_cospend_funders=20, cap_total=30)
        slice_sample = [all_txs[t] for t in node_ids if t in all_txs]
        if not slice_sample:
            print(json.dumps({"error": "no cached txs available; populate .cache first"}, indent=2))
        else:
            bounded_link_oracle = functools.partial(dss_link_oracle, budget_ms=200)   # hard-bounded: never blocks on a dense mix
            targets = [(slice_sample[0]["txid"], vout)
                      for vout in range(min(2, len(slice_sample[0].get("vout", []))))]
            out = run_offline(slice_sample, targets=targets, fetch=cache_fetch_tx,
                              link_oracle=bounded_link_oracle, seed=0)
            summary = {
                "n_clusters": out["n_clusters"],
                "n_cluster_nodes": out["n_cluster_nodes"],
                "m3_worst_partition_gap": out["m3_worst_partition_gap"],
                "m3_n_supernodes": out["m3_n_supernodes"],
                "targets": {f"{txid}:{vout}": {"min_entropy": t["min_entropy"],
                                               "fused_min_entropy": t.get("fused_min_entropy")}
                           for (txid, vout), t in out["report_targets"].items()},
            }
            print(json.dumps(summary, indent=2))

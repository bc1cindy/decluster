"""Cache-bounded REAL-data run of the N-S propagation driver (`decluster.propagate`), plus the
deferred union-find baseline (`decluster.cluster.cluster_naive`). Offline only: every ancestry
fetch reads `.cache/{txid}.json`; a cache MISS returns a boundary marker (coinbase-shaped, so
`ancestry.build_extended_graph`'s existing `_is_coinbase` check treats it as an absorber) instead
of ever hitting the network. See `results/RESULTS-ns-propagation.md` ("Real cache-bounded run")
for the numbers this produces and the honest reading of them.

Draws two INDEPENDENT same-owner signals from the cache so the union-find baseline (built from
co-spend) is not circular with the propagation seed labels (built from address reuse):

- co-spend clusters: a cached child tx whose inputs reference >=2 OTHER cached txids — a real
  common-input-ownership edge entirely inside the cache. Transitively closed (union-find) over
  ALL such edges. Feeds `cospend_clusters` (the split channel, `NSPropagator.refine`) and the
  union-find baseline (`cluster_naive`).
- address-reuse clusters: cached txs sharing an input address (M&N/BlockSci's other classic
  same-owner heuristic, independent of co-spend). Transitively closed the same way. Feeds
  `seed_labels` for `propagate`/`holdout_reid`.

Both are capped so the whole run (ancestry walk + linear-algebra solves + refine/propagate) stays
small — a couple of minutes, not a chain-scale claim.
"""
import glob
import json
import os

from decluster.unionfind import UF

HERE = os.path.dirname(__file__)
CACHE = os.path.join(HERE, "..", ".cache")

_BOUNDARY = {"txid": None, "vin": [{"is_coinbase": True}], "vout": []}


def cache_fetch_tx(txid):
    """Cache-only tx fetch: `.cache/{txid}.json` if present, else the boundary marker. Never
    touches the network — a miss becomes a provenance absorber, exactly like a real depth cutoff."""
    path = os.path.join(CACHE, txid + ".json")
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            return _BOUNDARY
    return _BOUNDARY


def load_cache_txs():
    """All real cached tx dicts (txid -> tx). The `.cache/*.json` glob also holds non-tx entries
    (block dumps, outspends, a stray block-hash string) sharing the extension; filter to dicts
    that actually look like a tx and are keyed by their own txid."""
    txs = {}
    for path in glob.glob(os.path.join(CACHE, "*.json")):
        if path.endswith(".outspends.json"):
            continue
        txid = os.path.basename(path)[:-5]
        try:
            tx = json.load(open(path))
        except Exception:
            continue
        if isinstance(tx, dict) and tx.get("txid") == txid and "vin" in tx and "vout" in tx:
            txs[txid] = tx
    return txs


def _uf_groups(items, edges, min_size=2):
    uf = UF(items)
    for a, b in edges:
        uf.union(a, b)
    groups = [sorted(g) for g in uf.groups() if len(g) >= min_size]
    groups.sort(key=lambda g: (len(g), g[0]))  # deterministic, smallest first
    return groups


def build_sample(all_txs, cap_cospend_funders=90, cap_total=150):
    """Bounded real sample: transitively-closed co-spend clusters (capped, plus the linking txs
    needed for `cluster_naive` to rediscover them from scratch) unioned with transitively-closed
    address-reuse clusters (capped to the remaining node budget). Returns
    (nodes, cospend_clusters, seed_labels)."""
    cached_ids = set(all_txs)

    linking = []  # (child_txid, [cached parent txids])
    for txid in sorted(all_txs):
        parents, seen = [], set()
        for v in all_txs[txid].get("vin", []):
            p = v.get("txid")
            if p and p in cached_ids and p not in seen:
                seen.add(p)
                parents.append(p)
        if len(parents) >= 2:
            linking.append((txid, sorted(parents)))

    funders_all = set()
    for _, parents in linking:
        funders_all.update(parents)
    cospend_edges = [(p[0], q) for _, p in linking for q in p[1:]]
    cospend_groups = _uf_groups(funders_all, cospend_edges)

    nodes, kept_cospend = set(), []
    for g in cospend_groups:
        cand = nodes | set(g)
        if len(cand) > cap_cospend_funders:
            continue
        nodes = cand
        kept_cospend.append(g)
    funder_set = set(nodes)
    children = [c for c, parents in linking if set(parents) <= funder_set]
    nodes |= set(children)

    by_addr = {}
    for txid in sorted(all_txs):
        for v in all_txs[txid].get("vin", []):
            a = (v.get("prevout") or {}).get("scriptpubkey_address")
            if a:
                by_addr.setdefault(a, set()).add(txid)
    addr_edges = [(sorted(ids)[0], x) for ids in by_addr.values() if len(ids) >= 2
                  for x in sorted(ids)[1:]]
    addr_groups = _uf_groups(all_txs.keys(), addr_edges)

    seed_labels, kept_addr = {}, 0
    for g in addr_groups:
        cand = nodes | set(g)
        if len(cand) > cap_total:
            continue
        nodes = cand
        label = f"addr_{kept_addr}"
        for txid in g:
            seed_labels[txid] = label
        kept_addr += 1

    return sorted(nodes), kept_cospend, seed_labels, children


def run_cache_bounded(depth=4, cap_cospend_funders=90, cap_total=150):
    from decluster.ancestry import build_extended_graph, absorber_distribution, dss_link_oracle
    from decluster.propagate import (NSPropagator, build_rarity, entity_signature,
                                     holdout_reid, partition_from_assignment)
    from decluster.graph_metric import partition_entropy
    from decluster.combiner import Combiner
    from decluster.cluster import cluster_naive

    all_txs = load_cache_txs()
    nodes, cospend_clusters, seed_labels, cospend_children = build_sample(
        all_txs, cap_cospend_funders, cap_total)

    node_sigs, node_txs, diag = {}, {}, {}
    for txid in nodes:
        node_txs[txid] = all_txs[txid]
        g = build_extended_graph((txid, 0), depth=depth, fetch=cache_fetch_tx,
                                 link_oracle=dss_link_oracle)
        dist = absorber_distribution(g, (txid, 0))
        node_sigs[txid] = entity_signature([dist])
        diag[txid] = {"n_absorbers": len(dist), "n_transient": len(g.transient),
                       "cache_miss_truncations": g.truncated}

    n_nodes = len(nodes)
    n_collapsed = sum(1 for d in diag.values() if d["n_absorbers"] <= 1)
    n_resolved = n_nodes - n_collapsed
    n_immediate_absorber = sum(1 for d in diag.values() if d["n_transient"] == 0)
    total_truncations = sum(d["cache_miss_truncations"] for d in diag.values())

    rarity = build_rarity(node_sigs.values())
    combiner = Combiner.from_library()
    prop = NSPropagator(rarity, combiner, theta=0.5, min_score=0.1, refuse_below=-2.0)

    before = seed_labels
    after = prop.propagate(node_sigs, seed_labels)
    reid = holdout_reid(node_sigs, seed_labels, prop)
    refined = prop.refine(cospend_clusters, node_sigs, node_txs)

    uf_groups = cluster_naive(nodes)
    cospend_member_set = {n for g in cospend_clusters for n in g}
    refined_full = refined + [[n] for n in nodes if n not in cospend_member_set]

    return {
        "n_nodes": n_nodes,
        "n_cospend_clusters": len(cospend_clusters),
        "n_cospend_children": len(cospend_children),
        "n_seed_labeled": len(seed_labels),
        "n_seed_groups": len(set(seed_labels.values())),
        "ancestry": {
            "depth": depth,
            "n_resolved_gt1_absorber": n_resolved,
            "n_collapsed_1_absorber": n_collapsed,
            "n_immediate_absorber_target_itself": n_immediate_absorber,
            "total_cache_miss_truncations": total_truncations,
        },
        "reid_rate": reid["rate"],
        "reid_hidden": reid["hidden"],
        "reid_recovered": reid["recovered"],
        "partition_bits_before": partition_entropy(partition_from_assignment(before)),
        "partition_bits_after": partition_entropy(partition_from_assignment(after)),
        "n_refined_groups": len(refined),
        "union_find": {
            "n_clusters": len(uf_groups),
            "entropy_bits": partition_entropy(uf_groups),
        },
        "refined_full": {
            "n_clusters": len(refined_full),
            "entropy_bits": partition_entropy(refined_full),
        },
    }


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(run_cache_bounded(), indent=2))

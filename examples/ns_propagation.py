"""Driver: run the N-S seed-and-propagate build-out on a tx sample and emit
results/RESULTS-ns-propagation.md. `run_on_signatures` is the offline-testable core;
`run` wires the real ancestry/entities/combiner modules."""
import statistics
from decluster.propagate import (NSPropagator, holdout_reid,
                                 partition_from_assignment)
from decluster.graph_metric import partition_entropy
from decluster.combiner import Combiner


def _median_cluster_bits(assigned):
    groups = partition_from_assignment(assigned)
    per = [partition_entropy([g]) for g in groups] or [0.0]
    return statistics.median(per)


def run_on_signatures(node_sigs, seed_labels, node_txs, rarity, combiner=None,
                      theta=0.5, min_score=0.1, refuse_below=-2.0, cospend_clusters=None):
    """Offline core: given precomputed signatures, run both channels and summarise.
    `before` = the seed labeling; `after` = the merge-propagated labeling. `refined` counts
    the split channel's output groups over the supplied co-spend clusters (empty if none)."""
    class _Agree:
        def score(self, a, b): return 3.0
    combiner = combiner or _Agree()
    prop = NSPropagator(rarity, combiner, theta=theta, min_score=min_score,
                        refuse_below=refuse_below)
    before = seed_labels
    after = prop.propagate(node_sigs, seed_labels)
    reid = holdout_reid(node_sigs, seed_labels, prop)
    refined = prop.refine(cospend_clusters or [], node_sigs, node_txs)
    return {"median_bits_before": _median_cluster_bits(before),
            "median_bits_after": _median_cluster_bits(after),
            "reid_rate": reid["rate"], "n_nodes": len(node_sigs),
            "n_refined_groups": len(refined)}


def run(txs, seeds, depth=6):
    """Real wiring: build per-node provenance signatures and rarity, then summarise.
    `txs` maps node -> representative tx dict; `seeds` maps node -> label."""
    from decluster.ancestry import ancestry_signature
    from decluster.propagate import build_rarity, entity_signature
    node_sigs = {}
    for node, tx in txs.items():
        coin = (tx["txid"], 0)
        node_sigs[node] = entity_signature([ancestry_signature(coin, depth=depth)])
    rarity = build_rarity(node_sigs.values())
    node_txs = {node: tx for node, tx in txs.items()}
    return run_on_signatures(node_sigs, seeds, node_txs, rarity,
                             combiner=Combiner.from_library())

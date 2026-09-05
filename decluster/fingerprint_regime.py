"""Compare two rarity rankings over the same library axes.

Both arms score `-log2(p)` on the same values from the same axes; the only difference is the
mismatch term. `fingerprint_ns.fingerprint_link` credits agreements only; `LibraryScorer` adds a
clamped mismatch penalty. Neither is a fitted Fellegi--Sunter model, so this comparison says
nothing about that method: it isolates the mismatch penalty.

The `ns_*` and `fs_*` result keys are the frozen artifact schema's names for the agreement-only
and agreement-plus-mismatch-penalty arms respectively, and are kept for that schema alone."""

from . import fingerprint_ns
from .change_gt import input_addrs
from .fingerprint_validate import LibraryScorer, reuse_pairs
from .graph_deanon import auc


def build_labeled_nodes(transactions, cap=200):
    """Assign each transaction to at most one address-reuse group."""
    by_address = {}
    for transaction in transactions:
        for address in sorted(input_addrs(transaction)):
            by_address.setdefault(address, {})[transaction["txid"]] = transaction
    nodes = []
    assigned = set()
    owner = 0
    for _, group in sorted(by_address.items()):
        members = [transaction for txid, transaction in sorted(group.items())
                   if txid not in assigned]
        if len(members) < 2:
            continue
        for transaction in members:
            assigned.add(transaction["txid"])
            nodes.append((transaction, owner))
        owner += 1
        if len(nodes) >= cap:
            break
    return nodes[:cap]


def evaluate(transactions, weights, label, pair_cap=2000, node_cap=200):
    """Evaluate pair ranking and candidate ranking under one weight source."""
    axes = fingerprint_ns.axis_fns()
    scorer = LibraryScorer()
    positives, negatives = reuse_pairs(transactions, cap=pair_cap, seed=0)
    agreement_only_auc = fingerprint_ns.pairwise_auc(positives, negatives, axes, weights)
    penalised_auc = auc(
        [scorer.score(a, b) for a, b in positives],
        [scorer.score(a, b) for a, b in negatives],
        0,
    )
    nodes = build_labeled_nodes(transactions, cap=node_cap)
    within_gaps = []
    agreement_only_exact = penalised_exact = evaluated = 0
    for index, (query, owner) in enumerate(nodes):
        candidates = [item for candidate_index, item in enumerate(nodes) if candidate_index != index]
        if not candidates:
            continue
        candidate_transactions = [transaction for transaction, _ in candidates]
        ns_result = fingerprint_ns.reid_gap(query, candidate_transactions, axes, weights)
        evaluated += 1
        if ns_result["best"] is not None and candidates[ns_result["best"]][1] == owner:
            agreement_only_exact += 1
        penalised = [scorer.score(query, transaction) for transaction in candidate_transactions]
        penalised_best = max(range(len(penalised)), key=penalised.__getitem__)
        if candidates[penalised_best][1] == owner:
            penalised_exact += 1
        key = fingerprint_ns.equivalence_key(query, axes)
        within_class = [transaction for transaction in candidate_transactions
                        if fingerprint_ns.equivalence_key(transaction, axes) == key]
        if len(within_class) >= 2:
            within_gaps.append(
                fingerprint_ns.reid_gap(query, within_class, axes, weights)["gap"]
            )
    return {
        "weight_source": label,
        "pair_positive_draws": len(positives),
        "pair_negative_draws": len(negatives),
        "candidate_queries": evaluated,
        "within_class_queries": len(within_gaps),
        "ns_auc": agreement_only_auc,
        "fs_auc": penalised_auc,
        "ns_top1": agreement_only_exact / evaluated if evaluated else 0.0,
        "fs_top1": penalised_exact / evaluated if evaluated else 0.0,
        "within_class_gap_mean": (
            sum(within_gaps) / len(within_gaps) if within_gaps else 0.0
        ),
    }

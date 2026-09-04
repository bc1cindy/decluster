"""Pair-level Bayesian and Fellegi-Sunter fingerprint comparison.

This module measures an attacker's record-linkage evidence.  It does not infer a
joint ownership partition and does not produce a defensive privacy score.
"""

from __future__ import annotations

from collections import defaultdict
import random

from .fingerprint_validate import LibraryScorer, reuse_pairs
from .fs_bayes import ece, gibbs_fit, pair_probs
from .fs_em import agree_matrix, em_fit, oracle_m
from .graph_deanon import auc
from .unionfind import UF


def _entity_counts(agreement, mask, u, m_samples, prior, pairs, node_count, seed, cap=200):
    rng = random.Random(seed)
    counts = []
    for m in m_samples[:cap]:
        probabilities = pair_probs(agreement, mask, m, u, prior)
        groups = UF(range(node_count))
        for (left, right), probability in zip(pairs, probabilities):
            if rng.random() < probability:
                groups.union(left, right)
        counts.append(len(groups.groups()))
    return counts


def _cluster_band(transactions, axes, u, m_samples, prior, em_m):
    node_count = len(transactions)
    pairs = [(left, right) for left in range(node_count) for right in range(left + 1, node_count)]
    agreement, mask, _, _ = agree_matrix(
        [(transactions[left], transactions[right]) for left, right in pairs], axes
    )
    counts = sorted(_entity_counts(
        agreement, mask, u, m_samples, prior, pairs, node_count, seed=0
    ))
    probabilities = pair_probs(agreement, mask, em_m, u, 0.5)
    groups = UF(range(node_count))
    for (left, right), probability in zip(pairs, probabilities):
        if probability >= 0.5:
            groups.union(left, right)
    return {
        "bayesian_mean": sum(counts) / len(counts),
        "bayesian_interval": [
            counts[int(0.025 * (len(counts) - 1))],
            counts[int(0.975 * (len(counts) - 1))],
        ],
        "fellegi_sunter_em_point": len(groups.groups()),
    }


def _reuse_nodes(transactions, cap=50):
    from .change_gt import input_addrs

    by_address = {}
    for transaction in transactions:
        for address in sorted(input_addrs(transaction)):
            by_address.setdefault(address, {})[transaction["txid"]] = transaction
    nodes = []
    for group in (list(group.values()) for group in by_address.values() if len(group) >= 2):
        if len(nodes) >= cap:
            break
        nodes.extend(group[:3])
    return nodes[:cap]


def _ambiguous_nodes(transactions, axes, m, u, pool_size=300, size=18, seed=1):
    rng = random.Random(seed)
    pool = rng.sample(transactions, min(pool_size, len(transactions)))
    pairs = [(left, right) for left in range(len(pool)) for right in range(left + 1, len(pool))]
    agreement, mask, _, _ = agree_matrix(
        [(pool[left], pool[right]) for left, right in pairs], axes
    )
    degrees = defaultdict(int)
    for (left, right), probability in zip(pairs, pair_probs(agreement, mask, m, u, 0.5)):
        if 0.2 <= probability <= 0.8:
            degrees[left] += 1
            degrees[right] += 1
    candidates = sorted(degrees)
    candidates.sort(key=degrees.__getitem__)
    step = max(1, len(candidates) // size)
    return [pool[index] for index in candidates[::step][:size]]


def evaluate(transactions, *, pair_cap=4000, seed=0, n_samples=2000, burn=500):
    """Evaluate three pair scorers on one balanced weak-label sample."""
    positive, negative = reuse_pairs(transactions, pair_cap, seed)
    pairs = positive + negative
    labels = [1] * len(positive) + [0] * len(negative)
    axes = LibraryScorer().axes
    agreement, mask, names, u = agree_matrix(pairs, axes)
    em = em_fit(agreement, mask, u)
    label_agreement = oracle_m(agreement, mask, labels)
    bayes = gibbs_fit(
        agreement, mask, u, n_samples=n_samples, burn=burn, seed=seed
    )

    scorers = (
        ("fellegi_sunter_fixed_0_95", pair_probs(agreement, mask, [0.95] * len(u), u, 0.5)),
        ("fellegi_sunter_em", pair_probs(agreement, mask, em["m"], u, 0.5)),
        ("bayesian_integrated_m", bayes["p_match"]),
    )
    discrimination = [
        {
            "scorer": name,
            "auc": auc(probabilities[:len(positive)], probabilities[len(positive):], seed),
            "ece": ece(probabilities, labels),
        }
        for name, probabilities in scorers
    ]
    per_axis = []
    for index, name in enumerate(names):
        per_axis.append({
            "axis": name,
            "bayesian_mean": bayes["m_mean"][index],
            "bayesian_interval": list(bayes["m_ci"][index]),
            "em": em["m"][index],
            "address_reuse_agreement": label_agreement[index],
            "fixed_assumption": 0.95,
        })

    clear = _reuse_nodes(transactions)
    ambiguous = _ambiguous_nodes(transactions, axes, em["m"], u)
    return {
        "transactions": len(transactions),
        "pairs": {"positive": len(positive), "negative": len(negative)},
        "discrimination": discrimination,
        "per_axis": per_axis,
        "cluster_diagnostics": {
            "clear_reuse_selected": {
                "nodes": len(clear),
                **_cluster_band(clear, axes, u, bayes["m_samples"], bayes["lam_mean"], em["m"]),
            },
            "borderline_selected": {
                "nodes": len(ambiguous),
                **_cluster_band(
                    ambiguous, axes, u, bayes["m_samples"], bayes["lam_mean"], em["m"]
                ),
            },
        },
    }

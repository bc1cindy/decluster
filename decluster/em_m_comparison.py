"""Unsupervised per-axis Fellegi-Sunter parameter diagnostic."""

from __future__ import annotations

from .fingerprint_validate import LibraryScorer, reuse_pairs
from .fs_em import agree_matrix, em_fit, oracle_m
from .graph_deanon import auc


def _score_pairs(scorer, positive, negative, seed):
    positive_scores = [scorer.score(left, right) for left, right in positive]
    negative_scores = [scorer.score(left, right) for left, right in negative]
    return auc(positive_scores, negative_scores, seed)


def evaluate(transactions, *, pair_cap=4000, seed=0):
    """Fit EM without labels, then evaluate against an address-reuse proxy."""
    positive, negative = reuse_pairs(transactions, pair_cap, seed)
    pairs = positive + negative
    labels = [1] * len(positive) + [0] * len(negative)
    axes = LibraryScorer().axes
    agreement, mask, names, collision = agree_matrix(pairs, axes)
    fit = em_fit(agreement, mask, collision)
    label_agreement = oracle_m(agreement, mask, labels)

    per_axis = [
        {
            "axis": name,
            "collision": collision[index],
            "em": fit["m"][index],
            "address_reuse_agreement": label_agreement[index],
            "fixed_assumption": 0.95,
        }
        for index, name in enumerate(names)
    ]
    em_values = dict(zip(names, fit["m"]))
    label_values = {
        name: value if value is not None else 0.95
        for name, value in zip(names, label_agreement)
    }
    pair_auc = {
        "fixed_0_95": _score_pairs(LibraryScorer(consistency=0.95), positive, negative, seed),
        "em": _score_pairs(LibraryScorer(consistency=em_values), positive, negative, seed),
        "address_reuse_agreement": _score_pairs(
            LibraryScorer(consistency=label_values), positive, negative, seed
        ),
    }
    return {
        "transactions": len(transactions),
        "pairs": {"positive": len(positive), "negative": len(negative)},
        "fit": {
            "inferred_pair_fraction": fit["lam"],
            "iterations": fit["n_iter"],
            "posterior_auc_against_address_reuse": auc(
                fit["r"][:len(positive)], fit["r"][len(positive):], seed
            ),
        },
        "per_axis": per_axis,
        "library_scorer_auc": pair_auc,
        "em_minus_fixed_auc": pair_auc["em"] - pair_auc["fixed_0_95"],
    }

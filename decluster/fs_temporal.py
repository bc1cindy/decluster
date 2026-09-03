"""Temporal, weak-label evaluation of fingerprint record linkage.

Address reuse supplies useful labels for an attack experiment, but it is not
independently verified ownership.  This module keeps that limitation in the
machine-readable result and never fits on transactions from the test period.
"""

from __future__ import annotations

import math
import random
from itertools import combinations

from .change_gt import input_addrs
from .fellegi_sunter import ComparisonField, comparison_vectors, fit_model_for_error_rates
from .fingerprint_validate import LibraryScorer
from .fs_bayes import ece
from .graph_deanon import exact_auc


def _height(tx):
    return (tx.get("status") or {}).get("block_height")


def temporal_split(txs, train_fraction=0.7):
    """Split at a block-height boundary; equal-height transactions never leak."""
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be strictly between zero and one")
    if any(_height(tx) is None for tx in txs):
        raise ValueError("every transaction needs status.block_height")
    heights = sorted({_height(tx) for tx in txs})
    if len(heights) < 2:
        raise ValueError("temporal evaluation needs at least two block heights")
    index = min(len(heights) - 2, max(0, int(len(heights) * train_fraction) - 1))
    cutoff = heights[index]
    train = [tx for tx in txs if _height(tx) <= cutoff]
    test = [tx for tx in txs if _height(tx) > cutoff]
    if not train or not test:
        raise ValueError("temporal split produced an empty partition")
    return train, test, cutoff


def weak_label_pairs(txs, cap=4000, seed=0):
    """Return balanced address-reuse/random pairs and their weak labels.

    Positives are distinct transactions sharing an input address.  Negatives
    are pairs with no observed shared input address.  Collaborative spends,
    address transfer, and unseen history can make either label wrong, hence the
    deliberate ``weak`` terminology.
    """
    if cap <= 0:
        raise ValueError("cap must be positive")
    rng = random.Random(seed)
    by_addr = {}
    addresses = {}
    by_txid = {}
    for tx in txs:
        tid = tx.get("txid")
        if not tid:
            raise ValueError("every transaction needs a txid")
        by_txid[tid] = tx
        aset = frozenset(input_addrs(tx))
        addresses[tid] = aset
        for address in sorted(aset):
            by_addr.setdefault(address, set()).add(tid)

    positive_ids = set()
    for tids in by_addr.values():
        for a, b in combinations(sorted(tids), 2):
            positive_ids.add((a, b))
    positive_ids = sorted(positive_ids)
    if len(positive_ids) > cap:
        positive_ids = rng.sample(positive_ids, cap)

    tids = sorted(by_txid)
    negative_ids = []
    seen = set()
    attempts = 0
    max_attempts = max(1000, cap * 100)
    while len(negative_ids) < min(cap, len(positive_ids)) and attempts < max_attempts:
        attempts += 1
        if len(tids) < 2:
            break
        a, b = sorted(rng.sample(tids, 2))
        if (a, b) in seen or addresses[a] & addresses[b]:
            continue
        seen.add((a, b))
        negative_ids.append((a, b))
    n = min(len(positive_ids), len(negative_ids))
    if not n:
        raise ValueError("both weak-label classes need at least one pair")
    positive_ids = positive_ids[:n]
    negative_ids = negative_ids[:n]
    pairs = ([(by_txid[a], by_txid[b]) for a, b in positive_ids] +
             [(by_txid[a], by_txid[b]) for a, b in negative_ids])
    return pairs, [True] * n + [False] * n


def fingerprint_fields():
    """Build binary comparisons for the same axes as ``LibraryScorer``."""
    scorer = LibraryScorer()
    fields = []
    for name, extractor, probabilities, _collision, _abstain in scorer.axes:
        active = frozenset(probabilities)

        def compare(left, right, extractor=extractor, active=active):
            a, b = extractor(left), extractor(right)
            if a not in active or b not in active:
                return None
            return a == b

        fields.append(ComparisonField(name, compare))
    return fields


def _usable_fields(vectors, labels, fields):
    usable = []
    for field in fields:
        match = any(label and vector.get(field.name) is not None
                    for vector, label in zip(vectors, labels))
        nonmatch = any(not label and vector.get(field.name) is not None
                       for vector, label in zip(vectors, labels))
        if match and nonmatch:
            usable.append(field)
    return usable


def _classification_metrics(labels, decisions):
    linked = [i for i, decision in enumerate(decisions) if decision == "link"]
    positives = sum(labels)
    tp = sum(labels[i] for i in linked)
    decided = [i for i, decision in enumerate(decisions) if decision != "review"]
    correct = sum((decisions[i] == "link") == labels[i] for i in decided)
    return {
        "true_positive": tp,
        "false_positive": len(linked) - tp,
        "false_negative": positives - tp,
        "precision": tp / len(linked) if linked else None,
        "recall": tp / positives if positives else None,
        "coverage": len(decided) / len(labels) if labels else 0.0,
        "selective_accuracy": correct / len(decided) if decided else None,
    }


def _score_metrics(scores, labels):
    """Exact Mann--Whitney AUC with half credit for ties (`graph_deanon.exact_auc`).

    Deliberately NOT `graph_deanon.auc`, which estimates the same quantity from 20,000 sampled
    draws: the AUCs in this module are differenced against each other, and a sampling error in the
    third decimal on each side is a large fraction of the delta. It does mean the numbers here are
    not directly comparable at three decimals with AUCs published elsewhere in this repository,
    which came from the estimator."""
    return {"auc": exact_auc(scores, labels)}


def _posterior(score, prior):
    log_odds = math.log(prior / (1.0 - prior)) + score * math.log(2.0)
    if log_odds >= 0:
        return 1.0 / (1.0 + math.exp(-log_odds))
    exp_odds = math.exp(log_odds)
    return exp_odds / (1.0 + exp_odds)


def evaluate_temporal(txs, *, train_fraction=0.7, cap=4000, seed=0,
                      false_match_rate=0.05, false_non_match_rate=0.05):
    """Fit early, evaluate late, and compare FS with rarity on identical pairs."""
    train_txs, test_txs, cutoff = temporal_split(txs, train_fraction)
    train_pairs, train_labels = weak_label_pairs(train_txs, cap, seed)
    test_pairs, test_labels = weak_label_pairs(test_txs, cap, seed + 1)

    fields = fingerprint_fields()
    train_vectors = comparison_vectors(train_pairs, fields)
    fields = _usable_fields(train_vectors, train_labels, fields)
    if not fields:
        raise ValueError("no comparison field has both weak-label classes in training")
    train_vectors = [{f.name: vector[f.name] for f in fields} for vector in train_vectors]
    test_vectors = comparison_vectors(test_pairs, fields)
    model = fit_model_for_error_rates(
        train_vectors, train_labels,
        false_match_rate=false_match_rate,
        false_non_match_rate=false_non_match_rate,
    )

    fs_scores = [model.score(vector) for vector in test_vectors]
    decisions = [model.classify(vector) for vector in test_vectors]
    rarity = LibraryScorer()
    rarity_scores = [rarity.score(left, right) for left, right in test_pairs]
    fs_metrics = _score_metrics(fs_scores, test_labels)
    rarity_metrics = _score_metrics(rarity_scores, test_labels)
    prior = sum(train_labels) / len(train_labels)
    probabilities = [_posterior(score, prior) for score in fs_scores]
    calibration = {
        "prior": prior,
        "brier": sum((p - int(y)) ** 2 for p, y in zip(probabilities, test_labels)) /
                 len(test_labels),
        "ece_10": ece(probabilities, [int(y) for y in test_labels], bins=10),
        "scope": "balanced weak-label case-control sample; not population calibration",
    }
    return {
        "label_provenance": {
            "kind": "weak_labels",
            "positive": "distinct transactions sharing an observed input address",
            "negative": "sampled pair with no observed shared input address",
            "independently_verified": False,
        },
        "split": {
            "strategy": "strict_block_height",
            "cutoff": cutoff,
            "train_height": [min(map(_height, train_txs)), max(map(_height, train_txs))],
            "test_height": [min(map(_height, test_txs)), max(map(_height, test_txs))],
            "train_transactions": len(train_txs),
            "test_transactions": len(test_txs),
        },
        "pairs": {
            "train_positive": sum(train_labels),
            "train_negative": len(train_labels) - sum(train_labels),
            "test_positive": sum(test_labels),
            "test_negative": len(test_labels) - sum(test_labels),
        },
        "fields": {
            name: {"m": parameter.m, "u": parameter.u,
                   "agreement_weight": parameter.agreement_weight,
                   "disagreement_weight": parameter.disagreement_weight}
            for name, parameter in model.parameters.items()
        },
        "fellegi_sunter": {
            **fs_metrics,
            **_classification_metrics(test_labels, decisions),
            "link": decisions.count("link"),
            "non_link": decisions.count("non-link"),
            "review": decisions.count("review"),
            "calibration": calibration,
        },
        "rarity_baseline": rarity_metrics,
        "comparison": {
            "same_test_pairs": True,
            "auc_delta_fs_minus_rarity": fs_metrics["auc"] - rarity_metrics["auc"],
        },
    }

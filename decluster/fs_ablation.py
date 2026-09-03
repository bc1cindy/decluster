"""Ablation of correlated comparison axes in the supervised Fellegi--Sunter model.

`decluster.fellegi_sunter` assumes conditional independence of comparison fields GIVEN match
status, and sums their log-likelihood weights. Several fingerprint axes plainly violate that
assumption (fields derived from the same script type, the same signature encoding, or the same
wallet behaviour move together). This module measures the damage rather than assuming it:

1. Within-class association (`class_conditional_association`): unconditional correlation between
   two fields is expected even under a perfectly valid FS model, because matches and non-matches
   differ systematically on every predictive axis -- pooling the two classes induces spurious
   association (a Simpson's-paradox-style confound). The FS assumption is about association WITHIN
   each class, so that is what is measured here, separately for the match and non-match class, via
   the phi coefficient (see `phi_coefficient`).
2. Leave-one-out ablation (`leave_one_out`): refit and re-evaluate out-of-period with each field
   removed, on identical held-out pairs, reporting the change in held-out AUC and classification
   metrics. A field whose removal does not hurt is carrying no independent information.
3. Group ablation (`group_ablation`): for a cluster of mutually dependent fields, compare removing
   the whole cluster against removing every member but one representative.

Stdlib only -- no scipy/numpy/pandas.
"""

from __future__ import annotations

import math
from itertools import combinations

from .fellegi_sunter import comparison_vectors, fit_model_for_error_rates
from .fs_temporal import (
    _classification_metrics,
    fingerprint_fields,
    temporal_split,
    weak_label_pairs,
)
from .graph_deanon import exact_auc

__all__ = [
    "phi_coefficient",
    "class_conditional_association",
    "most_dependent_pairs",
    "dependent_clusters",
    "leave_one_out",
    "group_ablation",
    "run_ablation_study",
]


def phi_coefficient(a_values, b_values):
    """Matthews/phi correlation between two parallel sequences of booleans.

    ``phi = (n11*n00 - n10*n01) / sqrt((n11+n10)(n01+n00)(n11+n01)(n10+n00))`` where ``nXY`` counts
    how often the pair took agree-value X for the first field and Y for the second (1 = agree, 0 =
    disagree). This is exactly the Pearson correlation coefficient specialised to two binary
    variables. Returns ``None`` when any marginal is degenerate (all-agree or all-disagree on
    either field), where phi is undefined rather than zero.
    """
    n11 = n10 = n01 = n00 = 0
    for a, b in zip(a_values, b_values):
        if a and b:
            n11 += 1
        elif a and not b:
            n10 += 1
        elif not a and b:
            n01 += 1
        else:
            n00 += 1
    denom = (n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00)
    if denom == 0:
        return None
    return (n11 * n00 - n10 * n01) / math.sqrt(denom)


def class_conditional_association(vectors, labels, fields, min_n=30):
    """Pairwise phi coefficient between comparison fields, WITHIN each class separately.

    Restricts each pair to the pairs where both fields are active (non-``None``) and where the
    label matches the class being measured. This is deliberately NOT the unconditional correlation
    over the full sample: the FS conditional-independence assumption is about association given
    match status, and unconditional correlation would be dominated by the two classes' different
    base rates on every axis, proving nothing about the assumption FS actually makes.

    Returns ``{"match": {(name_a, name_b): {"phi": float, "n": int}}, "non_match": {...}}``,
    restricted to pairs with at least ``min_n`` jointly-active observations and a defined phi.
    Field-name pairs are ordered as given by ``fields`` (alphabetical, since callers use
    ``fingerprint_fields()``, whose names are already sorted by the underlying axis order).
    """
    names = [field.name for field in fields]
    result = {"match": {}, "non_match": {}}
    for cls, want in (("match", True), ("non_match", False)):
        idx = [i for i, label in enumerate(labels) if bool(label) == want]
        for a, b in combinations(names, 2):
            av, bv = [], []
            for i in idx:
                va, vb = vectors[i].get(a), vectors[i].get(b)
                if va is None or vb is None:
                    continue
                av.append(va)
                bv.append(vb)
            if len(av) < min_n:
                continue
            phi = phi_coefficient(av, bv)
            if phi is not None:
                result[cls][(a, b)] = {"phi": phi, "n": len(av)}
    return result


def most_dependent_pairs(association, top_n=10):
    """Rank field pairs by the larger-magnitude phi seen in either class.

    Returns a list of ``(pair, phi_match, phi_non_match)`` tuples, ``phi_match``/``phi_non_match``
    each ``None`` when that class had too few observations to score the pair, sorted by
    ``max(|phi_match|, |phi_non_match|)`` descending.
    """
    pairs = set(association["match"]) | set(association["non_match"])

    def rank_key(pair):
        m = association["match"].get(pair)
        n = association["non_match"].get(pair)
        return max(abs(m["phi"]) if m else 0.0, abs(n["phi"]) if n else 0.0)

    ranked = sorted(pairs, key=rank_key, reverse=True)
    out = []
    for pair in ranked[:top_n]:
        m = association["match"].get(pair)
        n = association["non_match"].get(pair)
        out.append((pair, m["phi"] if m else None, n["phi"] if n else None))
    return out


def dependent_clusters(association, threshold=0.6):
    """Connected components of fields joined by an edge when |phi| >= `threshold` in either class.

    `threshold=0.6` (conventionally a "strong" phi coefficient) is a fixed, stated choice, not
    fitted to the data. Single-linkage connected components can chain transitively (A-B and B-C
    strong does not mean A-C is), so a returned cluster is a claim about the connectivity structure
    at this threshold, not that every pair inside it is individually strongly associated -- callers
    that need that should check `association` directly. Singletons (fields joined to nothing) are
    dropped; only clusters of two or more fields are returned.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for cls in ("match", "non_match"):
        for (a, b), data in association[cls].items():
            if abs(data["phi"]) >= threshold:
                union(a, b)

    groups = {}
    for field in list(parent):
        groups.setdefault(find(field), set()).add(field)
    clusters = [group for group in groups.values() if len(group) > 1]
    clusters.sort(key=lambda group: (-len(group), sorted(group)))
    return clusters


def _usable_names(vectors, labels, names):
    """Names with both a match and a non-match observation active, mirroring
    `fs_temporal._usable_fields` but over plain field names rather than `ComparisonField` objects,
    since ablation works by deleting keys from already-built comparison vectors."""
    usable = []
    for name in names:
        match = any(label and vector.get(name) is not None
                    for vector, label in zip(vectors, labels))
        nonmatch = any(not label and vector.get(name) is not None
                       for vector, label in zip(vectors, labels))
        if match and nonmatch:
            usable.append(name)
    return usable


def _fit_eval(train_vectors, train_labels, test_vectors, test_labels, drop=frozenset(), *,
              false_match_rate=0.05, false_non_match_rate=0.05):
    """Refit on `train_vectors` with the fields in `drop` removed, then score `test_vectors`."""
    def strip(vector):
        return {name: value for name, value in vector.items() if name not in drop}

    stripped_train = [strip(vector) for vector in train_vectors]
    stripped_test = [strip(vector) for vector in test_vectors]
    names = _usable_names(stripped_train, train_labels,
                          sorted({name for vector in stripped_train for name in vector}))
    if not names:
        raise ValueError("no comparison field survives this ablation")
    train_v = [{name: vector[name] for name in names if name in vector} for vector in stripped_train]
    test_v = [{name: vector[name] for name in names if name in vector} for vector in stripped_test]
    model = fit_model_for_error_rates(
        train_v, train_labels,
        false_match_rate=false_match_rate, false_non_match_rate=false_non_match_rate,
    )
    scores = [model.score(vector) for vector in test_v]
    decisions = [model.classify(vector) for vector in test_v]
    return {
        "fields": names,
        "model": model,
        "auc": exact_auc(scores, test_labels),
        **_classification_metrics(list(test_labels), decisions),
    }


def _split_and_vectorize(txs, train_fraction, cap, seed):
    train_txs, test_txs, cutoff = temporal_split(txs, train_fraction)
    train_pairs, train_labels = weak_label_pairs(train_txs, cap, seed)
    test_pairs, test_labels = weak_label_pairs(test_txs, cap, seed + 1)
    fields = fingerprint_fields()
    train_vectors = comparison_vectors(train_pairs, fields)
    test_vectors = comparison_vectors(test_pairs, fields)
    return train_vectors, train_labels, test_vectors, test_labels, cutoff


def leave_one_out(txs, *, train_fraction=0.7, cap=4000, seed=0,
                  false_match_rate=0.05, false_non_match_rate=0.05):
    """Refit and re-evaluate out-of-period with each usable field removed, one at a time.

    Uses the identical held-out pairs for every ablation (same temporal split, same weak-label
    pairs) so `auc_delta` isolates the effect of removing that one field. A field whose removal
    does not hurt (`auc_delta` near zero or negative) is carrying no independent information once
    the rest of the model is fit -- exactly what a correlated, redundant axis looks like.
    """
    train_vectors, train_labels, test_vectors, test_labels, cutoff = _split_and_vectorize(
        txs, train_fraction, cap, seed)
    baseline = _fit_eval(train_vectors, train_labels, test_vectors, test_labels,
                         false_match_rate=false_match_rate, false_non_match_rate=false_non_match_rate)
    per_field = {}
    for name in baseline["fields"]:
        ablated = _fit_eval(train_vectors, train_labels, test_vectors, test_labels, drop={name},
                            false_match_rate=false_match_rate,
                            false_non_match_rate=false_non_match_rate)
        per_field[name] = {
            "auc": ablated["auc"],
            "auc_delta": baseline["auc"] - ablated["auc"],
            "coverage": ablated["coverage"],
            "selective_accuracy": ablated["selective_accuracy"],
        }
    return {
        "cutoff": cutoff,
        "baseline": {k: v for k, v in baseline.items() if k != "model"},
        "leave_one_out": per_field,
    }


def group_ablation(txs, group, *, train_fraction=0.7, cap=4000, seed=0,
                   false_match_rate=0.05, false_non_match_rate=0.05):
    """Compare removing a whole correlated `group` against removing every member but one.

    The representative kept is the group member with the largest `|agreement_weight|` in the
    train-fitted full model -- the single field in the group that alone carries the most
    discriminative signal, chosen from train-side fit parameters only (no test-side information
    enters the choice). If the group is genuinely redundant, `remove_group_delta` should exceed
    `keep_representative_delta` by a wide margin: dropping every correlated copy loses real
    information, dropping all-but-one loses almost none.
    """
    group = set(group)
    if len(group) < 2:
        raise ValueError("a group needs at least two fields")
    train_vectors, train_labels, test_vectors, test_labels, cutoff = _split_and_vectorize(
        txs, train_fraction, cap, seed)
    baseline = _fit_eval(train_vectors, train_labels, test_vectors, test_labels,
                         false_match_rate=false_match_rate, false_non_match_rate=false_non_match_rate)
    missing = group - set(baseline["fields"])
    if missing:
        raise ValueError(f"group contains fields absent from the fitted model: {sorted(missing)}")
    representative = max(group, key=lambda name: abs(baseline["model"].parameters[name].agreement_weight))

    remove_group = _fit_eval(train_vectors, train_labels, test_vectors, test_labels, drop=group,
                             false_match_rate=false_match_rate,
                             false_non_match_rate=false_non_match_rate)
    keep_representative = _fit_eval(
        train_vectors, train_labels, test_vectors, test_labels, drop=group - {representative},
        false_match_rate=false_match_rate, false_non_match_rate=false_non_match_rate)
    return {
        "cutoff": cutoff,
        "group": sorted(group),
        "representative": representative,
        "baseline_auc": baseline["auc"],
        "remove_group_auc": remove_group["auc"],
        "remove_group_delta": baseline["auc"] - remove_group["auc"],
        "keep_representative_auc": keep_representative["auc"],
        "keep_representative_delta": baseline["auc"] - keep_representative["auc"],
    }


def run_ablation_study(txs, *, train_fraction=0.7, ablation_cap=4000,
                       association_cap=8000, seed=0, association_min_n=30,
                       cluster_threshold=0.6,
                       false_match_rate=0.05, false_non_match_rate=0.05):
    """The full study: within-class association, leave-one-out, and group ablation on every
    cluster the association step finds. Association is measured on the train side of the same
    temporal split leave-one-out and group ablation use, with a larger pair cap for statistical
    power -- it is a diagnostic about the axes' joint distribution, not a held-out performance
    claim, so it does not need to be evaluated out-of-period, but it is still computed only from
    data available before the cutoff to keep every number in this module "fit early"."""
    train_txs, _test_txs, cutoff = temporal_split(txs, train_fraction)
    fields = fingerprint_fields()
    assoc_pairs, assoc_labels = weak_label_pairs(train_txs, association_cap, seed)
    assoc_vectors = comparison_vectors(assoc_pairs, fields)
    association = class_conditional_association(assoc_vectors, assoc_labels, fields,
                                                 min_n=association_min_n)
    top_pairs = most_dependent_pairs(association, top_n=15)
    clusters = dependent_clusters(association, threshold=cluster_threshold)

    loo = leave_one_out(txs, train_fraction=train_fraction, cap=ablation_cap, seed=seed,
                        false_match_rate=false_match_rate, false_non_match_rate=false_non_match_rate)
    groups = [
        group_ablation(txs, cluster, train_fraction=train_fraction, cap=ablation_cap, seed=seed,
                       false_match_rate=false_match_rate, false_non_match_rate=false_non_match_rate)
        for cluster in clusters
    ]
    return {
        "cutoff": cutoff,
        "association": {
            "statistic": "phi coefficient (Pearson correlation of two binary agree/disagree "
                         "indicators), computed within each class separately",
            "min_n": association_min_n,
            "cap": association_cap,
            "most_dependent_pairs": [
                {"fields": list(pair), "phi_match": phi_match, "phi_non_match": phi_non_match}
                for pair, phi_match, phi_non_match in top_pairs
            ],
            "cluster_threshold": cluster_threshold,
            "clusters": [sorted(cluster) for cluster in clusters],
        },
        "leave_one_out": loo,
        "group_ablation": groups,
    }

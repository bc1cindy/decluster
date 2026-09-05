"""Layer 4 — N-S fingerprint channel: a tx's fingerprint as a sparse {(axis,value): bits}
quasi-identifier, scored by rarity-weighted agreement overlap. Reuses propagate.eccentricity
for the acceptance gap. Measures whether fingerprints are sparse quasi-identifiers or
equivalence-class conditioners (see results/RESULTS-fingerprint-regime.md). Offline.

WHAT THIS ACTUALLY IMPLEMENTS. A rarity-weighted agreement overlap between two fingerprints. Two
departures from the cited algorithm, both deliberate and neither hidden: (1) the feature weight is
the self-information `-log2(p)` of the value (`library_weights`, `measured_weights`), where the
paper's similarity weights a shared attribute by `1/log|support|` — the form this repo does keep in
`ancestry.provenance_link`; a rare value is up-weighted under both, but the two are different
functions and are not interchangeable. (2) `reid_gap` computes the eccentricity gap and RETURNS it;
nothing in this module gates on it, so no candidate is ever refused for being a diffuse tie — the
refusal is left to the caller. There is no seed set, no propagation and no second view here either.
This repository holds no faithful implementation of the cited algorithm; the module closest to it
is `decluster.reid`, itself declared an adaptation. (`decluster/baselines/narayanan_shmatikov.py`
is a different paper: the 2009 social-graph propagation kernel, not this record-matching one.)"""

import json
import math
from collections import Counter


def axis_fns():
    """[(axis_name, extractor_fn)] from the canonical library axis list."""
    from .fingerprint_validate import LibraryScorer
    return [(name, fn) for name, fn, *_ in LibraryScorer().axes]


def fingerprint_signature(tx, axis_fns, weights):
    """Sparse {(axis, value): bits} vector. A feature is kept only when weights carries a bit
    for (axis, value) — an unmeasured value is not evidence, so it is dropped (never credited)."""
    sig = {}
    for name, fn in axis_fns:
        key = (name, fn(tx))
        w = weights.get(key)
        if w is not None:
            sig[key] = w
    return sig


def fingerprint_link(sig_a, sig_b):
    """Rarity-weighted overlap over agreeing features (same axis AND same value). Agreements
    only — no mismatch penalty, which is the one term the rarity combiner adds and this channel
    drops."""
    return sum(w for k, w in sig_a.items() if k in sig_b)


def library_weights():
    """{(axis, value): -log2(p)} from the library's measured shares."""
    from .fingerprint_validate import LibraryScorer
    out = {}
    for name, fn, p, *_ in LibraryScorer().axes:
        for v, pv in p.items():
            if pv > 0:
                out[(name, v)] = -math.log2(pv)
    return out


def measured_weights(txs, axis_fns):
    """{(axis, value): -log2(share)} re-measured on txs (share within each axis)."""
    counts = {name: Counter() for name, _ in axis_fns}
    for tx in txs:
        for name, fn in axis_fns:
            counts[name][fn(tx)] += 1
    out = {}
    for name, c in counts.items():
        tot = sum(c.values())
        for v, k in c.items():
            if k > 0:
                out[(name, v)] = -math.log2(k / tot)
    return out


def lumen_weights(prior_path, fallback):
    """{(axis, value): bits} from the lumen prior JSON, falling back to `fallback` per feature."""
    out = dict(fallback)
    with open(prior_path) as f:
        prior = json.load(f)
    for axis, vals in prior.items():
        for v, bits in vals.items():
            out[(axis, v)] = bits
    return out


def pairwise_auc(pos_pairs, neg_pairs, axis_fns, weights, seed=0):
    """AUC of fingerprint_link separating same-owner pos_pairs from neg_pairs."""
    from .graph_deanon import auc

    def link(pair):
        a, b = pair
        return fingerprint_link(fingerprint_signature(a, axis_fns, weights),
                                fingerprint_signature(b, axis_fns, weights))
    return auc([link(p) for p in pos_pairs], [link(p) for p in neg_pairs], seed)


CONDITIONING_AXES = ("input_script_type", "nsequence", "input_order", "output_order", "version")


def equivalence_key(tx, axis_fns, cond_axes=CONDITIONING_AXES):
    """The tx's values on the conditioning axes; equal keys ⇒ one fingerprint equivalence class."""
    fn = dict(axis_fns)
    return tuple(fn[a](tx) for a in cond_axes if a in fn)


def reid_gap(query, candidates, axis_fns, weights):
    """Rank candidates by fingerprint_link vs query; return top index, eccentricity gap, top score."""
    from .single_view_propagation import eccentricity
    q = fingerprint_signature(query, axis_fns, weights)
    scores = [fingerprint_link(q, fingerprint_signature(c, axis_fns, weights)) for c in candidates]
    if not scores:
        return {"best": None, "gap": 0.0, "best_score": 0.0}
    best = max(range(len(scores)), key=lambda i: scores[i])
    return {"best": best, "gap": eccentricity(scores), "best_score": scores[best]}

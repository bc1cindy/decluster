"""M1 §04-faithful fusion harness: per-target graph-only vs §04-fused provenance min-entropy.

`anonymity_set.provenance_anonymity_fused` folds a subjective link matrix into the backward walk
BEFORE the absorbing solve (`build_extended_graph(..., subjective_oracle=...)`), the link-level
fusion post-04 describes ("a matrix that combines with the ones derived from the graph") — sharper,
and structurally different, than the post-solve `reweight`/`decay` demonstrated in
`examples/anonymity_set.py` (RESULTS-anonymity-set.md sections (a)-(c)), which only reshuffles mass
across the *already-solved* boundary distribution and can never route mass through a specific
interior edge the way link-level fusion can.

The concrete subjective oracle here is `sameowner_link_oracle` driven by
`extractors._change_index(tx)` — a REAL decluster signal, not a fabricated one: on a genuine 2-output
tx it identifies the less-round output as change, which is same-owner as every input by construction
(no fetch/outspends needed — this is a pure function of the tx's own vout values, so it works fully
offline over `.cache/`). `same_owner_pairs(tx) = {(i, change_idx) for i in range(n_inputs)}` when
`_change_index` resolves, else `set()` (abstain — `sameowner_link_oracle` then returns None and
`build_extended_graph` falls back to the graph-only link matrix for that hop, per its own contract).

Reuses `examples/anonymity_set.py`'s bounded-slice + hard-bounded (subprocess-killed) link-oracle
pattern verbatim (`hard_bounded_link_oracle`, `_same_owner_pairs` over real address-reuse clusters)
to avoid the same CoinJoin-scale subset-sum hangs documented there — see that module's docstring.
Depth is kept small (2) and the target pool bounded, matching the source harness.

Offline over `.cache/`. Reproduce: `.venv/bin/python -m examples.anonymity_set_fused`."""
import json

from decluster.ancestry import build_extended_graph, absorber_distribution
from decluster.anonymity_set import anonymity_bits, sameowner_link_oracle
from decluster.extractors import _change_index
from examples.anonymity_set import hard_bounded_link_oracle, _same_owner_pairs
from examples.ns_propagation_cache_run import cache_fetch_tx, load_cache_txs

DEPTH = 2
N_TARGETS = 40


def _change_same_owner_pairs(tx):
    """The concrete §04 subjective signal: change is same-owner as every input (real, not
    fabricated) — `{(i, change_idx) for i in range(n_inputs)}`, or empty (abstain) when
    `_change_index` can't resolve a change output (not a clean 2-out tx, or a tie)."""
    ci = _change_index(tx)
    if ci is None:
        return set()
    return {(i, ci) for i in range(len(tx.get("vin", [])))}


def _counting_oracle(boost=9.0):
    """Wraps `sameowner_link_oracle` with call/hit counters. `build_extended_graph` only invokes
    the subjective oracle on interior coins it actually resolves a link matrix for (not on
    coinbase/depth-cutoff absorbers, and not on hops the hard-bounded link oracle truncates) — so
    `calls` is exactly the count of interior txs the fused walk visited, and `hits` is how many of
    those had a resolvable `_change_index` (a real same-owner pin fired), giving an honest coverage
    measure of the concrete signal on the real, truncation-bounded walk (not a separate, untruncated
    BFS that would overcount past what the walk itself ever reaches)."""
    stats = {"calls": 0, "hits": 0}

    def same_owner_pairs(tx):
        stats["calls"] += 1
        pairs = _change_same_owner_pairs(tx)
        if pairs:
            stats["hits"] += 1
        return pairs
    return sameowner_link_oracle(same_owner_pairs, boost=boost), stats


def _walk(target, depth=DEPTH, subjective_oracle=None):
    g = build_extended_graph(target, depth=depth, fetch=cache_fetch_tx,
                              link_oracle=hard_bounded_link_oracle,
                              subjective_oracle=subjective_oracle)
    return absorber_distribution(g, target), g.truncated


def _origin_key(origin):
    txid, vout = origin
    return f"{txid}:{vout}"


def _jsonify(dist):
    return {_origin_key(o): p for o, p in dist.items()}


def run(depth=DEPTH, n_targets=N_TARGETS):
    all_txs = load_cache_txs()
    pairs = _same_owner_pairs(all_txs, n_targets)

    results = []
    for target_txid, ref_txid in pairs:
        target = (target_txid, 0)
        graph_dist, graph_truncated = _walk(target, depth)
        graph_bits = anonymity_bits(graph_dist)
        oracle, stats = _counting_oracle(boost=9.0)
        fused_dist, fused_truncated = _walk(target, depth, subjective_oracle=oracle)
        fused_bits = anonymity_bits(fused_dist)
        hits, n_interior = stats["hits"], stats["calls"]

        results.append({
            "target": target_txid,
            "n_absorbers_graph": len(graph_dist),
            "n_absorbers_fused": len(fused_dist),
            "graph_truncated": graph_truncated,
            "fused_truncated": fused_truncated,
            "graph_min_entropy": graph_bits["min_entropy"],
            "graph_shannon": graph_bits["shannon"],
            "fused_min_entropy": fused_bits["min_entropy"],
            "fused_shannon": fused_bits["shannon"],
            "sharpened": fused_bits["min_entropy"] < graph_bits["min_entropy"] - 1e-9,
            "change_signal_hits": hits,
            "change_signal_interior_txs": n_interior,
            "graph_dist": _jsonify(graph_dist),
            "fused_dist": _jsonify(fused_dist),
        })
    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))

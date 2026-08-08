"""M1 offline harness: per-target provenance anonymity set. Computes the graph-only min-entropy
(`ancestry.absorber_distribution`, the post-04 anonymity set), folds in subjective hypotheses
(`anonymity_set.provenance_overlap_hypothesis` against a real same-owner-labelled reference coin,
then two further narrowing steps), and reports the entropy-DECAY table
(`anonymity_set.decay`) demonstrating: (a) graph-only min-entropy, (b) a confidence-1 indicator
collapsing the distribution to a point mass (the F-S special case), (c) narrowing hypotheses
monotonically shrinking min-entropy (the post-06 anonymity-set decay).

Offline over `.cache/` (reuses `examples.ns_propagation_cache_run`'s cache-bounded slice and
same-owner (address-reuse) labels — no network).

Tractability: this repo's own probing found the exact subset-sum oracle (`dss.pairwise_link_prob`)
hangs well past its own `budget_ms` on some real cached txs — not only the obvious CoinJoin-scale
ones (277 in / 325 out), but also small-looking ones with dense/similar values (3 in / 37 out hung
>30s; a 27-in/2-out tx with near-equal input values likewise). `budget_ms` is cooperative and the
native call does not appear to check it (or does not release control) inside the blow-up; a
Python-level `signal.alarm` also failed to preempt it (the call never yields to the interpreter).
So `hard_bounded_link_oracle` below runs each link computation in a throwaway subprocess and
kills it on a wall-clock deadline — an OS-level bound that works regardless of what the native
code does internally. A kill returns None, which is exactly `ancestry`'s own oracle-refusal
boundary: `build_extended_graph` already truncates cleanly on None, so no core-code change is
needed."""
import json
import multiprocessing as mp

from decluster.ancestry import build_extended_graph, absorber_distribution
from decluster.anonymity_set import (
    anonymity_bits, provenance_anonymity, decay, provenance_overlap_hypothesis,
)
from examples.ns_propagation_cache_run import cache_fetch_tx, load_cache_txs, build_sample

DEPTH = 2
N_TARGETS = 40  # generous cap; the real same-owner pool (address-reuse clusters) is smaller
WALL_MS = 1200
MAX_ORIGIN_SIGS = 12  # cap per-origin sub-walks so one wide boundary can't blow up the run


def _link_worker(inputs, outputs, budget_ms, q):
    import dss
    try:
        q.put(dss.pairwise_link_prob(inputs, outputs, budget_ms))
    except BaseException:
        # dss can hard-panic (pyo3_runtime.PanicException, a BaseException) on pathological
        # inputs, e.g. a `set.len() <= 64` assertion seen on a 27-input tx during this harness's
        # own probing; treat that the same as a normal refusal.
        q.put(None)


def hard_bounded_link_oracle(inputs, outputs, wall_ms=WALL_MS):
    """dss_link_oracle wrapped with a hard, non-cooperative wall-clock bound (see module docstring).
    Times out -> None (truncate), same contract as `ancestry.dss_link_oracle`."""
    q = mp.Queue()
    p = mp.Process(target=_link_worker, args=(inputs, outputs, wall_ms, q))
    p.start()
    p.join(wall_ms / 1000.0 + 0.5)
    if p.is_alive():
        p.terminate()
        p.join(0.5)
        if p.is_alive():
            p.kill()
            p.join()
        return None
    try:
        return q.get_nowait()
    except Exception:
        return None


def _same_owner_pairs(all_txs, n):
    """(target, reference) pairs from real address-reuse clusters (>=2 members) — a genuine
    same-owner label, not a fabricated one. Sorted by the pair's own tx size (smallest first) so
    the cheapest, safest walks run first; the hard-bounded oracle still guards every hop
    regardless of what a parent transaction turns out to be."""
    _, _, seed_labels, _ = build_sample(all_txs)
    by_label = {}
    for txid, label in seed_labels.items():
        by_label.setdefault(label, []).append(txid)

    def own_size(txid):
        tx = all_txs[txid]
        return len(tx.get("vin", [])) + len(tx.get("vout", []))

    pairs = [(m[0], m[1]) for _, m in sorted(by_label.items()) if len(m) >= 2]
    pairs.sort(key=lambda pr: own_size(pr[0]) + own_size(pr[1]))
    return pairs[:n]


def _walk(target, depth=DEPTH):
    g = build_extended_graph(target, depth=depth, fetch=cache_fetch_tx,
                              link_oracle=hard_bounded_link_oracle)
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
        target, reference = (target_txid, 0), (ref_txid, 0)
        base_dist, truncated = _walk(target, depth)
        graph_bits = anonymity_bits(base_dist)
        entry = {
            "target": target_txid, "reference": ref_txid,
            "n_absorbers": len(base_dist), "truncated": truncated,
            "graph_min_entropy": graph_bits["min_entropy"],
            "graph_shannon": graph_bits["shannon"],
            "base_dist": _jsonify(base_dist),
        }

        if len(base_dist) < 2:
            entry["skipped"] = "graph-collapsed to a single boundary atom (0 bits already)"
            results.append(entry)
            continue

        reference_sig, _ = _walk(reference, depth)
        origins = list(base_dist)[:MAX_ORIGIN_SIGS]
        sig_of = {o: (base_dist if o == target else _walk(o, depth)[0]) for o in origins}

        h1 = provenance_overlap_hypothesis(reference_sig, origins, sig_of=sig_of,
                                            name="provenance_overlap(same-owner ref)")
        argmax_base = max(base_dist, key=base_dist.get)
        h1_contains_argmax = h1[1].get(argmax_base, 0.0) >= 1.0

        dist1 = provenance_anonymity(target, [h1], base_dist=base_dist)
        top1 = max(dist1, key=dist1.get)
        h2 = ("entity_narrowing(reinforce top candidate)",
              {o: (1.0 if o == top1 else 0.1) for o in base_dist})

        dist2 = provenance_anonymity(target, [h1, h2], base_dist=base_dist)
        top2 = max(dist2, key=dist2.get)
        h3 = ("indicator_confidence1(illustrative F-S case)",
              {o: (1.0 if o == top2 else 0.0) for o in base_dist})

        trace = decay(base_dist, [h1, h2, h3])
        entry["reference_n_absorbers"] = len(reference_sig)
        entry["h1_kept_graph_argmax"] = h1_contains_argmax
        entry["decay_trace"] = [(name, bits) for name, bits in trace]
        entry["monotone"] = all(b <= a + 1e-9 for a, b in zip(
            [bits for _, bits in trace], [bits for _, bits in trace][1:]))
        results.append(entry)
    return results


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))

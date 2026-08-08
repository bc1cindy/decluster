"""Live depth-5 validation of the PUBLIC `analyze()` facade (decluster/analyze.py) — the
systematic-callability proof this facade exists for. `analyze()` is the thin orchestration layer an
external consumer (e.g. wasabi-model) imports to get per-coin §04 fused provenance anonymity sets;
this harness runs it over real Wasabi-scale coinjoin round txids, at `depth=5`, behind the
panic-safe `decluster.oracle.bounded_link_oracle`, and checks three things honestly:

1. It never crashes (the whole point of the panic-safe oracle layer — `truncated` absorbs an
   oracle refusal, no exception should ever surface through `analyze()`).
2. It resolves non-trivial origins (n_absorbers > 1) on real coinjoin-shaped transactions, deeper
   than the shallow `.cache`-only walk other examples exercise at lower depth.
3. It counts DEEP (ancestral) fusion emergence: a target whose fused min-entropy sharpens below its
   graph-only min-entropy from a same-owner link found somewhere back in the ancestry walk, not from
   the target's own transaction's address reuse (§06/robustness predicts this is rare — see
   `results/RESULTS-analyze.md`).

This is a live, non-deterministic `examples/` harness (network + subprocess-capable oracle
internals) — NOT part of the asserted test suite. Live-only imports (`decluster.fetch`,
`examples.anonymity_set_scale`, and even `decluster`'s own `analyze`/`bounded_link_oracle`, per the
task-5 spec) are deferred inside `analyze_live`'s body so `import examples.analyze_live` never
touches the network.

usage: .venv/bin/python -m examples.analyze_live [max_targets] [cap_total] [budget_ms] [depth]
"""
from decluster.anonymity_set import address_reuse_pairs


def analyze_live(round_txids=None, depth=5, budget_ms=6000, max_targets=8, cap_total=60):
    """Run the PUBLIC analyze() facade over real coinjoin rounds via live fetch, at `depth`, with the
    panic-safe bounded oracle — the systematic-callability proof on real Wasabi-scale data.

    round_txids: coinjoin round txids to analyze (default: examples.anonymity_set_scale.seed_targets()
        sliced to cap_total — real multi-input coinjoin-shaped txs from local history).
    Returns {"n_targets": int, "crashes": int, "resolved_nontrivial": int (n_absorbers>1),
             "mean_absorbers": float, "mean_min_entropy": float, "deep_fusion": int (targets where
             fused<graph AND the reuse/link is NOT in the target's own tx), "per_target": [...]}.
    """
    from decluster import analyze, bounded_link_oracle
    from decluster.fetch import fetch_tx
    from examples.anonymity_set_scale import seed_targets

    if round_txids is None:
        round_txids = list(seed_targets())[:cap_total]

    oracle = bounded_link_oracle(budget_ms)
    per_target = []
    crashes = 0

    for txid in round_txids[:max_targets]:
        entry = {"txid": txid, "crashed": False}
        try:
            result = analyze(txid, targets=[0], depth=depth, fetch=fetch_tx, link_oracle=oracle,
                             with_origins=True)
            r0 = result[0]
            prov = r0["provenance"]
            fused = r0.get("fused")
            entry.update({
                "n_absorbers": prov["n_absorbers"],
                "min_entropy": prov["min_entropy"],
                "fused_min_entropy": fused["min_entropy"] if fused else None,
                "truncated": r0["truncated"],
            })
            deep = False
            if fused is not None and fused["min_entropy"] < prov["min_entropy"] - 1e-9:
                try:
                    own_fired = bool(address_reuse_pairs(fetch_tx(txid)))
                    deep = not own_fired
                except Exception:
                    pass   # can't verify the own-tx boundary -> don't credit it as deep
            entry["deep_fusion"] = deep
        except BaseException as e:
            # the panic-safe oracle should make this unreachable -- crashes must stay 0.
            crashes += 1
            entry["crashed"] = True
            entry["error"] = repr(e)
        per_target.append(entry)

    resolved = [e for e in per_target if not e["crashed"]]
    resolved_nontrivial = [e for e in resolved if e["n_absorbers"] > 1]
    deep_fusion = [e for e in resolved if e["deep_fusion"]]

    return {
        "n_targets": len(per_target),
        "crashes": crashes,
        "resolved_nontrivial": len(resolved_nontrivial),
        "mean_absorbers": (sum(e["n_absorbers"] for e in resolved) / len(resolved)) if resolved else 0.0,
        "mean_min_entropy": (sum(e["min_entropy"] for e in resolved) / len(resolved)) if resolved else 0.0,
        "deep_fusion": len(deep_fusion),
        "per_target": per_target,
    }


if __name__ == "__main__":
    import json
    import sys

    max_targets = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    cap_total = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    budget_ms = int(sys.argv[3]) if len(sys.argv) > 3 else 6000
    depth = int(sys.argv[4]) if len(sys.argv) > 4 else 5

    summary = analyze_live(depth=depth, budget_ms=budget_ms, max_targets=max_targets,
                           cap_total=cap_total)
    print(json.dumps(summary, indent=2, default=str))

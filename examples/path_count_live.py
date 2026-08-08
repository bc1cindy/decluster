"""Live end-to-end proof of the two things task 5/6 shipped: (a) `max_nodes` tames the deep-coinjoin
`analyze(depth=5, path_count=True)` call that `RESULTS-analyze.md` (b) found hung past a 25-minute
wall cap uncapped — bounded, it returns fast with a truncated LOWER BOUND, never a crash; (b) the §07
path-count object (`decluster.path_count.path_count_anonymity`) is a genuinely different
(multiplicity-weighted / robustness) lens from §04's set-size entropy on the SAME tractable envelope
(§07 does not extend it — see `RESULTS-path-counting-analysis.md`).

This is a live, non-deterministic `examples/` harness (network + subprocess-capable oracle
internals) — NOT part of the asserted test suite. Live-only imports (`decluster.fetch`,
`examples.anonymity_set_scale`, and even `decluster`'s own `analyze`/`bounded_link_oracle`) are
deferred inside each function's body so `import examples.path_count_live` never touches the network.

usage:
  .venv/bin/python -m examples.path_count_live bounded [round_txid] [depth] [max_nodes] [budget_ms]
  .venv/bin/python -m examples.path_count_live sweep [txid] [budget_ms]
"""


def bounded_coinjoin(round_txid=None, depth=5, max_nodes=400, budget_ms=3000):
    """Prove the bounded walk tames a deep coinjoin: analyze() with `max_nodes` at `depth=5` over a
    real coinjoin round txid returns FAST (seconds, not the 25-minute hang `RESULTS-analyze.md` (b)
    hit uncapped) with a truncated LOWER BOUND, and never crashes.

    round_txid: a real coinjoin-shaped txid (default: the first `examples.anonymity_set_scale.
    seed_targets()` entry). Times one `analyze(round_txid, targets=[0], depth=depth,
    max_nodes=max_nodes, link_oracle=bounded_link_oracle(budget_ms), path_count=True)` call inside
    `try/except BaseException` — crashes must stay 0 (the panic-safe oracle + max_nodes cap should
    make an escaped exception unreachable).

    Returns {"txid", "secs", "crashed": bool, "n_origins", "min_entropy", "truncated",
             "path_log_W": float}."""
    from decluster import analyze, bounded_link_oracle
    from decluster.fetch import fetch_tx
    from examples.anonymity_set_scale import seed_targets
    import time

    if round_txid is None:
        targets = seed_targets()
        if not targets:
            raise RuntimeError("no seed_targets() available to pick a default round_txid")
        round_txid = targets[0]

    oracle = bounded_link_oracle(budget_ms)
    entry = {"txid": round_txid, "crashed": False}
    t0 = time.monotonic()
    try:
        result = analyze(round_txid, targets=[0], depth=depth, fetch=fetch_tx, link_oracle=oracle,
                         max_nodes=max_nodes, path_count=True)
        secs = time.monotonic() - t0
        r0 = result[0]
        prov = r0["provenance"]
        pc = r0.get("path_count") or {}
        entry.update({
            "secs": secs,
            "n_origins": prov["n_absorbers"],
            "min_entropy": prov["min_entropy"],
            "truncated": r0["truncated"],
            "path_log_W": pc.get("log_W_paths"),
        })
    except BaseException as e:
        # the panic-safe oracle + max_nodes cap should make this unreachable -- crashes must stay 0.
        entry["secs"] = time.monotonic() - t0
        entry["crashed"] = True
        entry["error"] = repr(e)
    return entry


def sweep_vs_s04(txid="00264b9175b14c6a783610ed39da33a2717a4494bfefee08d8e5cdd7e7ebc23f",
                 depths=(1, 2, 3, 4, 5), budget_ms=3000):
    """§04 vs §07 contrast on a NARROW (tractable) tx across depths: for each depth, run
    `analyze(txid, depth=depth, path_count=True)` once and report the §04 provenance
    (min_entropy/n_origins, link-probability/set-size) beside the §07 path_count
    (min_entropy/log_W_paths, multiplicity-weighted/robustness) -- the SAME envelope, two different
    lenses, showing they need not agree.

    Returns [{"depth", "n_origins", "s04_min_entropy", "s07_min_entropy", "log_W_paths",
              "truncated", "crashed"}]."""
    from decluster import analyze, bounded_link_oracle
    from decluster.fetch import fetch_tx

    oracle = bounded_link_oracle(budget_ms)
    rows = []
    for d in depths:
        row = {"depth": d, "crashed": False}
        try:
            e = analyze(txid, targets=[0], depth=d, fetch=fetch_tx, link_oracle=oracle,
                        path_count=True)[0]
            prov = e["provenance"]
            pc = e.get("path_count") or {}
            row.update({
                "n_origins": prov["n_absorbers"],
                "s04_min_entropy": prov["min_entropy"],
                "s07_min_entropy": pc.get("min_entropy"),
                "log_W_paths": pc.get("log_W_paths"),
                "truncated": e["truncated"],
            })
        except BaseException as ex:
            row.update({"crashed": True, "error": repr(ex)})
        rows.append(row)
    return rows


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        # .venv/bin/python -m examples.path_count_live sweep [txid] [budget_ms]
        txid = sys.argv[2] if len(sys.argv) > 2 else \
            "00264b9175b14c6a783610ed39da33a2717a4494bfefee08d8e5cdd7e7ebc23f"
        budget_ms = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
        print(json.dumps(sweep_vs_s04(txid, budget_ms=budget_ms), indent=2, default=str))
    else:
        # .venv/bin/python -m examples.path_count_live bounded [round_txid] [depth] [max_nodes] [budget_ms]
        round_txid = sys.argv[2] if len(sys.argv) > 2 else None
        depth = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        max_nodes = int(sys.argv[4]) if len(sys.argv) > 4 else 400
        budget_ms = int(sys.argv[5]) if len(sys.argv) > 5 else 3000
        print(json.dumps(bounded_coinjoin(round_txid, depth=depth, max_nodes=max_nodes,
                                          budget_ms=budget_ms), indent=2, default=str))

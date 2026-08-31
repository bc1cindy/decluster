"""Pin the graph structural de-anonymization on a committed real slice: a contiguous 2016 mainnet
block range (400000-400004, addresses only) exported via `bigquery/graph.sql` and frozen at
`tests/fixtures/graph_deanon_2016.ndjson.gz`. The common-neighbours structural score separates
same-owner pairs from random. The documented era AUCs (`results/RESULTS-graph-deanon.md`: full
0.992, payment 0.950, shuffle 0.500) reproduce on this slice; pinned as a band with a shuffle control
at chance. This is graph structure (cit 24 territory), not the amount or ancestry sparsity channels."""
import gzip
import json
import os

from decluster.graph_deanon import evaluate

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "graph_deanon_2016.ndjson.gz")


def _sample():
    seen, out = set(), []
    with gzip.open(FIX, "rt") as f:
        for line in f:
            tx = json.loads(line)
            tid = tx.get("txid")
            if tid and tid not in seen:
                seen.add(tid)
                out.append((tx, int(tx.get("height", 0))))
    return out


def test_structural_score_deanonymises_the_real_slice():
    r = evaluate(_sample(), seed=0)
    assert r["pos_pairs"] > 1000 and r["neg_pairs"] > 100
    assert r["auc_payment"] >= 0.85           # honest (no co-spend) separation; doc ~0.950
    assert r["auc_full"] >= 0.90              # co-spend + payment; doc ~0.992
    assert 0.40 <= r["auc_shuffle"] <= 0.60    # shuffled-label control at chance

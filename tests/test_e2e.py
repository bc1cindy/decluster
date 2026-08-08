import functools
import math

import pytest

from examples.e2e import run_offline

_CACHE_MIN_TXS = 50   # below this a bounded slice isn't a meaningful real-data exercise


def _fixture():
    # A non-trivial connected slice, all offline/deterministic:
    #   t1: report target, 2 inputs with DISTINCT prevout addresses "a"/"b" (funded by coinbase
    #       parents pa/pb, outside `sample`); output 1 reuses input 0's address "a" (address-reuse
    #       subjective source fires).
    #   t2: a second, address-disjoint tx (input address "c", funded by coinbase pc, outside
    #       `sample`) — together with t1 this gives contract_cospend >= 2 distinct super-nodes
    #       (M3 gate is non-trivial: n > 1, not the degenerate single-partition case).
    #   t3: co-spends t1's and t2's outputs as its own two inputs — a REAL common-input-ownership
    #       edge for cluster_refined to merge t1/t2 on (not a stub, not a trivial 1-node slice).
    txs = {
        "t1": {"txid": "t1", "locktime": 0,
               "vin": [{"txid": "pa", "vout": 0, "sequence": 0xFFFFFFFF,
                        "prevout": {"value": 500, "scriptpubkey_address": "a"}},
                       {"txid": "pb", "vout": 0, "sequence": 0xFFFFFFFF,
                        "prevout": {"value": 500, "scriptpubkey_address": "b"}}],
               "vout": [{"value": 600, "scriptpubkey_address": "z"},
                        {"value": 399, "scriptpubkey_address": "a"}]},
        "t2": {"txid": "t2", "locktime": 0,
               "vin": [{"txid": "pc", "vout": 0, "sequence": 0xFFFFFFFF,
                        "prevout": {"value": 700, "scriptpubkey_address": "c"}}],
               "vout": [{"value": 690, "scriptpubkey_address": "c"}]},
        "t3": {"txid": "t3", "locktime": 0,
               "vin": [{"txid": "t1", "vout": 1, "sequence": 0xFFFFFFFF, "prevout": {"value": 399}},
                       {"txid": "t2", "vout": 0, "sequence": 0xFFFFFFFF, "prevout": {"value": 690}}],
               "vout": [{"value": 1080}]},
        "pa": {"txid": "pa", "vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
        "pb": {"txid": "pb", "vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
        "pc": {"txid": "pc", "vin": [{"is_coinbase": True}], "vout": [{"value": 700}]},
    }
    return txs


def test_e2e_offline_pipeline_holds_invariants():
    txs = _fixture()
    fetch = lambda txid: txs[txid]
    uniform = lambda ins, outs: [[1.0] * len(outs) for _ in ins]
    sample = [txs["t1"], txs["t2"], txs["t3"]]
    out = run_offline(sample, targets=[("t1", 0), ("t1", 1)], fetch=fetch,
                      link_oracle=uniform, seed=0)
    # (a) report ran, fused is conservative for every target
    for t in out["report_targets"].values():
        assert t["fused_min_entropy"] <= t["min_entropy"] + 1e-9
    # (b) M3 gate is non-trivial (>= 2 super-nodes — not the degenerate 1-partition case) and the
    # sampler matches exact enumeration on it
    assert out["m3_n_supernodes"] >= 2
    assert out["m3_worst_partition_gap"] < 0.05
    # (c) cluster_refined ran for real over >= 2 nodes and returned a non-trivial grouping (some
    # group merges more than one node — not every node its own singleton)
    assert out["n_cluster_nodes"] >= 2
    assert out["n_clusters"] >= 1
    assert any(len(g) > 1 for g in out["cluster_groups"])
    # (d) the cluster_refined -> §04 source is LIVE, not inert: assert on the EXACT cluster_of the
    # PIPELINE built and fed the report — not a locally rebuilt one. If the wiring regressed to the
    # txid-keyed map (the bug this bridge fixes), out["cluster_of"] would be keyed by txids, address
    # lookups would miss, and cluster_pairs would fire nothing — failing both asserts below.
    from decluster.anonymity_set import cluster_pairs
    cof = out["cluster_of"]
    assert cof.get("a") is not None and cof.get("a") == cof.get("b")   # address-keyed; inputs of t1 share an owner
    cp = cluster_pairs(txs["t1"], cof)
    assert (1, 1) in cp   # (input1 "b", output1 "a") — cluster source, beyond address-reuse's (0,1)


def _cache_available():
    try:
        from examples.ns_propagation_cache_run import load_cache_txs
        return len(load_cache_txs()) >= _CACHE_MIN_TXS
    except Exception:
        return False


@pytest.mark.skipif(not _cache_available(),
                    reason=f"requires a populated .cache/ (>= {_CACHE_MIN_TXS} real cached txs)")
def test_e2e_real_cache_slice_holds_invariants_nontrivially():
    from examples.ns_propagation_cache_run import build_sample, cache_fetch_tx, load_cache_txs
    from decluster.ancestry import dss_link_oracle

    all_txs = load_cache_txs()
    node_ids, *_ = build_sample(all_txs, cap_cospend_funders=20, cap_total=30)
    sample = [all_txs[t] for t in node_ids if t in all_txs]
    assert sample, "bounded cache slice must be non-empty"
    bounded_link_oracle = functools.partial(dss_link_oracle, budget_ms=200)   # hard-bounded, offline (cache-only fetch)
    targets = [(sample[0]["txid"], vout) for vout in range(min(2, len(sample[0].get("vout", []))))]

    out = run_offline(sample, targets=targets, fetch=cache_fetch_tx,
                      link_oracle=bounded_link_oracle, seed=0)

    for t in out["report_targets"].values():
        assert t["fused_min_entropy"] <= t["min_entropy"] + 1e-9
    assert out["m3_n_supernodes"] >= 2
    assert out["m3_worst_partition_gap"] < 0.05
    assert out["n_clusters"] >= 1

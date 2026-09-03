import pytest

from decluster.analyze import analyze, cluster_map, cluster_posterior


def _fetch_factory():
    # t1 vout0 "z": no subjective pin. t1 vout1 "a": reuses input0's prevout address "a" ->
    # address-reuse subjective source fires, sharpening the fused readout below graph-only.
    txs = {
        "t1": {"txid": "t1",
               "vin": [{"txid": "p0", "vout": 0, "prevout": {"value": 500, "scriptpubkey_address": "a"}},
                       {"txid": "p1", "vout": 0, "prevout": {"value": 500}}],
               "vout": [{"value": 600, "scriptpubkey_address": "z"},
                        {"value": 399, "scriptpubkey_address": "a"}]},
        "p0": {"txid": "p0", "vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
        "p1": {"txid": "p1", "vin": [{"is_coinbase": True}], "vout": [{"value": 500}]},
    }
    return lambda txid: txs[txid], txs


def _uniform(ins, outs):
    return [[1.0] * len(outs) for _ in ins]


def test_shape_has_provenance_and_fused_by_default():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], targets=[0], depth=1, fetch=fetch, link_oracle=_uniform)
    t = out[0]
    p = t["provenance"]
    assert set(p) == {"min_entropy", "shannon", "n_absorbers", "origins"}
    assert "truncated" in t
    assert "fused" in t


def test_txid_input_fetches_the_tx():
    fetch, _ = _fetch_factory()
    out = analyze("t1", targets=[0], fetch=fetch, link_oracle=_uniform, depth=1)
    assert 0 in out


def test_targets_none_covers_every_spendable_output():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], depth=1, fetch=fetch, link_oracle=_uniform)
    assert set(out) == {0, 1}


def test_with_origins_false_omits_origins():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], targets=[0], depth=1, fetch=fetch, link_oracle=_uniform, with_origins=False)
    assert "origins" not in out[0]["provenance"]


def test_fused_is_conservative_for_every_target():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], depth=1, fetch=fetch, link_oracle=_uniform)
    for t in out.values():
        assert t["fused"]["min_entropy"] <= t["provenance"]["min_entropy"] + 1e-9


def test_subjective_false_omits_fused():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], targets=[0], depth=1, fetch=fetch, link_oracle=_uniform, subjective=False)
    assert "fused" not in out[0]


def test_address_reuse_pin_sharpens_the_fused_reading():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], targets=[1], depth=1, fetch=fetch, link_oracle=_uniform)
    t = out[1]
    assert t["fused"]["min_entropy"] < t["provenance"]["min_entropy"]


def test_path_count_true_adds_path_count_block():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], targets=[0], depth=1, fetch=fetch, link_oracle=_uniform,
                  path_count=True)
    pc = out[0]["path_count"]
    assert set(pc) == {"min_entropy", "shannon", "origins_weighted"}


def test_path_count_false_by_default_omits_the_key():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], targets=[0], depth=1, fetch=fetch, link_oracle=_uniform)
    assert "path_count" not in out[0]


def test_max_nodes_bounds_the_walk():
    txs = _cospend_fixture()
    fetch = lambda txid: txs[txid]
    out_full = analyze(txs["t3"], targets=[0], depth=6, fetch=fetch, link_oracle=_uniform)
    out_capped = analyze(txs["t3"], targets=[0], depth=6, fetch=fetch, link_oracle=_uniform,
                         max_nodes=1)
    assert out_capped[0]["truncated"] > out_full[0]["truncated"]


def test_new_params_default_preserves_prior_entry_shape():
    fetch, txs = _fetch_factory()
    out = analyze(txs["t1"], targets=[0], depth=1, fetch=fetch, link_oracle=_uniform)
    t = out[0]
    assert set(t) == {"provenance", "fused", "truncated"}
    assert set(t["provenance"]) == {"min_entropy", "shannon", "n_absorbers", "origins"}


def _cospend_fixture():
    # Same t1/t2/t3 shape as tests/test_e2e.py::_fixture(): t1 (inputs "a"/"b"), t2 (input "c"),
    # t3 co-spends t1's and t2's outputs as its own two inputs -> a real common-input-ownership
    # edge for cluster_refined to merge t1/t2 on, and >= 2 M3 co-spend super-nodes.
    return {
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


def test_cluster_map_is_address_keyed_not_txid_keyed():
    txs = _cospend_fixture()
    fetch = lambda txid: txs[txid]
    cof = cluster_map(["t1", "t2", "t3"], fetch=fetch)
    assert "a" in cof
    assert "t1" not in cof
    assert cof.get("a") == cof.get("b")   # t1's two inputs share an owner via t3's co-spend


def test_cluster_posterior_matches_exact_enumeration():
    txs = _cospend_fixture()
    out = cluster_posterior([txs["t1"], txs["t2"], txs["t3"]], seed=0)
    assert out["n_supernodes"] >= 2
    assert out["worst_partition_gap"] < 0.05
    assert out["coassignment"]
    for (i, j), p in out["coassignment"].items():
        assert i < j
        assert 0.0 <= p <= 1.0

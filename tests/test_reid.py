"""The record-linkage capstone: sparsity predicts de-anonymization (Narayanan-Shmatikov
Theorem 2), measured with the same Algorithm 1B primitives the engine uses. A frozen fixture
of real ancestry signatures (`tests/fixtures/reid_sigs.json.gz`, labelled by each coin's own
nearest-neighbour similarity) reproduces the gap; the synthetic tests pin the mechanism."""

import gzip
import json
import os

from decluster.reid import (build_rarity, reid_attack, stratify, stratified_reid,
                            top_similarity)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "reid_sigs.json.gz")


def _load_fixture():
    fix = json.load(gzip.open(FIXTURE, "rt"))
    coins = list(fix)
    sigs = {c: {a: v for a, v in fix[c]["sig"].items()} for c in coins}
    tops = {c: fix[c]["top"] for c in coins}
    return coins, sigs, tops


def test_sparsity_predicts_deanonymization_on_real_signatures():
    """On real ancestry signatures, the attack de-anonymizes sparse coins and abstains on
    dense ones. The de-anonymization rate (exact hits / attackable) is the honest end-to-end
    metric; the gap between the strata is the Theorem 2 link."""
    coins, sigs, tops = _load_fixture()
    sparse = [c for c in coins if tops[c] < 0.5]
    dense = [c for c in coins if tops[c] >= 0.9]
    assert len(sparse) > 3 * len(dense) > 0        # real data is overwhelmingly sparse
    rarity = build_rarity(sigs.values())
    chance = 1.0 / len(coins)

    ds, es, ts = reid_attack(sparse, coins, sigs, rarity, m=8)
    dd, ed, td = reid_attack(dense, coins, sigs, rarity, m=8)
    sparse_rate = es / ts                          # de-anon rate on sparse
    dense_rate = ed / td                           # de-anon rate on dense

    assert es / ds == 1.0                           # every sparse match is exact (precision 1)
    assert sparse_rate > 0.7                        # sparse coins de-anonymize
    assert sparse_rate > 3 * dense_rate             # the Theorem 2 gap
    assert sparse_rate > 50 * chance                # far above the a-priori baseline
    assert dd / td < 0.5                            # the gate abstains on dense coins


def _synthetic():
    # sparse coins: disjoint ancestor sets (orthogonal, no twin); dense coins: twin pairs.
    sigs = {}
    for i in range(20):
        sigs[f"s{i}"] = {f"s{i}_{k}": 1.0 for k in range(6)}
    for p in range(4):
        anc = {f"d{p}_{k}": 1.0 for k in range(6)}
        sigs[f"d{p}a"] = dict(anc)
        sigs[f"d{p}b"] = dict(anc)             # exact twin
    return list(sigs), sigs


def test_stratify_separates_sparse_and_dense():
    coins, sigs = _synthetic()
    sparse, dense, top = stratify(coins, sigs)
    assert set(sparse) == {c for c in coins if c.startswith("s")}
    assert set(dense) == {c for c in coins if c.startswith("d")}


def test_attack_pins_sparse_and_abstains_on_twins():
    coins, sigs = _synthetic()
    rarity = build_rarity(sigs.values())
    sparse = [c for c in coins if c.startswith("s")]
    dense = [c for c in coins if c.startswith("d")]

    d, e, t = reid_attack(sparse, coins, sigs, rarity, m=4)
    assert e == t and t == len(sparse)             # every sparse coin pinned exactly

    d2, e2, t2 = reid_attack(dense, coins, sigs, rarity, m=4)
    assert d2 == 0                                  # a twin has no eccentric winner: abstain


def test_top_similarity_is_zero_for_disjoint_and_one_for_twins():
    coins, sigs = _synthetic()
    top = top_similarity(coins, sigs)
    assert top["s0"] == 0.0
    assert top["d0a"] >= 0.999

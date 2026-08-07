"""Regression test pinning the intersection channel against a real mainnet co-spend.

`RESULTS-intersection.md` reports a run over a real co-spend: the monitor stops at one spender and
makes a candidate of the other, four branches resolve to real ancestor sets, their intersection is
empty without being blind, and the engine refuses the odd funder out despite the co-spend prior.

The measured values are pinned here as data so the behaviour is checked without the network. What is
*not* pinned is the chain: if a fixture and the chain ever disagree, this file is the stale one.

    parent   0cb4870cf2dfa387…  12 in / 21 out
    spenders 66fcf6a888e26f66…  29 in / 21 out  (a mix by the stop rule)
             5cce9a7fa309eabd…  19 in / 20 out  (one input below it)
"""

import pytest

from decluster.intersect import evaluate, score_candidate
from decluster.monitor import walk_frontier

PARENT = "0cb4870c"
MIX = "66fcf6a8"        # 29 in / 21 out — at or above the threshold on both sides
CANDIDATE = "5cce9a7f"  # 19 in / 20 out — one input below it

# The four funders whose backward walks resolve, and what they resolved to.
FUNDERS = ["64ef93f2", "ace0615d", "4db038e3", "b3803654"]
SIZES = [16, 24, 26, 9]
TRUNCATED = [5, 4, 10, 0]
FINGERPRINT_ALIKE = 6.82   # measured between the first three
FINGERPRINT_ODD = -4.06    # measured between b3803654 and each of the others


def _chain():
    """The two spends of the parent's outputs, reduced to what the walk reads."""
    txs = {
        PARENT: {"vin": [{}] * 12, "vout": [{}] * 21},
        MIX: {"vin": [{}] * 29, "vout": [{}] * 21},
        CANDIDATE: {"vin": [{}] * 19, "vout": [{}] * 20},
    }
    spends = {PARENT: [{"spent": True, "txid": CANDIDATE}, {"spent": True, "txid": CANDIDATE},
                       {"spent": True, "txid": MIX}, {"spent": True, "txid": MIX}]}
    return txs.__getitem__, lambda t: spends.get(t, [{"spent": False}] * 21)


def test_the_stop_rule_separates_the_two_spenders_by_one_input():
    """29-in/21-out is a mix and halts the walk; 19-in/20-out is one input under
    the threshold and becomes a candidate. The boundary is that close on real data."""
    get_tx, get_outspends = _chain()
    out = walk_frontier(
        [(PARENT, i) for i in range(4)], get_tx, get_outspends, max_depth=0
    )
    assert [c["txid"] for c in out["candidates"]] == [CANDIDATE]
    assert out["candidates"][0]["shape"] == (19, 20)
    assert sum(e["reason"] == "coinjoin" for e in out["frontier"]) == 2


def test_four_branches_resolve_and_their_intersection_is_empty_but_not_blind():
    """Every branch contributes at least one observed origin, so the empty
    intersection is a result rather than an absence of vision."""
    ops = [(f, 0) for f in FUNDERS]
    # Disjoint supports of the measured sizes; the real ancestors are not the point,
    # the shape of the answer is.
    sigs = {
        op: {f"{f}-{k}": 1.0 / n for k in range(n)}
        for op, f, n in zip(ops, FUNDERS, SIZES)
    }
    truncs = dict(zip(ops, TRUNCATED))
    out = evaluate(
        {"txid": CANDIDATE, "outpoints": ops},
        sigs.__getitem__,
        truncation_of=truncs.__getitem__,
    )
    assert out["sizes"] == SIZES
    assert out["truncated"] == TRUNCATED
    assert out["blind"] is False, "no branch is pure truncation"
    assert out["shared"] == []
    assert out["collapsed_bits"] is None, "an empty intersection is not unbounded narrowing"


def test_the_engine_refuses_the_odd_funder_despite_the_cospend(monkeypatch):
    """The co-spend says one owner; the fingerprint says otherwise for one branch,
    and the engine splits it out. This is the step the channel exists for."""
    import decluster.cluster as cluster

    nodes = FUNDERS + [CANDIDATE]
    txs = {n: {"txid": n, "vin": [{"txid": "root"}], "vout": [{"value": 1000}]} for n in FUNDERS}
    txs[CANDIDATE] = {"txid": CANDIDATE, "vin": [{"txid": f} for f in FUNDERS],
                      "vout": [{"value": 3900}]}
    monkeypatch.setattr(cluster, "fetch_tx", txs.__getitem__)

    class Measured:
        def score(self, a, b):
            pair = {a["txid"], b["txid"]}
            return FINGERPRINT_ODD if "b3803654" in pair else FINGERPRINT_ALIKE

    out = score_candidate(
        {"txid": CANDIDATE, "outpoints": [(f, 0) for f in FUNDERS]},
        lambda ns, sigs=None: cluster.cluster_refined(ns, Measured(), amount=False),
        lambda op: op[0],
    )
    assert out["believed"] is False
    assert len(out["refused_pairs"]) == 3, "the odd funder is refused against each of the others"
    assert all(r[3] == pytest.approx(FINGERPRINT_ODD) for r in out["refused_pairs"])
    assert sorted(len(g) for g in out["groups"]) == [1, 4], "split 4/1, not merged"

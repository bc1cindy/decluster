import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.graph_deanon import CoSpent, build


def _tx(ins, outs, txid=None):
    d = {"vin": [{"prevout": {"scriptpubkey_address": a}} for a in ins],
         "vout": [{"scriptpubkey_address": a} for a in outs]}
    if txid:
        d["txid"] = txid
    return d


def _naive(sample):
    """The quadratic pair set CoSpent replaces, kept here as the reference to agree with."""
    pairs = set()
    for tx, _ in sample:
        a = [v["prevout"]["scriptpubkey_address"] for v in tx["vin"]]
        for i in range(len(a)):
            for j in range(i + 1, len(a)):
                pairs.add(frozenset((a[i], a[j])))
    return pairs


def test_agrees_with_the_pair_set_it_replaces():
    sample = [(_tx(["a", "b", "c"], ["x"]), None),
              (_tx(["c", "d"], ["y"]), None),
              (_tx(["e"], ["z"]), None),
              (_tx(["a", "e"], ["w"]), None)]
    _uf, neigh, _pay, cospent = build(sample)
    naive = _naive(sample)
    addrs = sorted(neigh)
    for i in range(len(addrs)):
        for j in range(i + 1, len(addrs)):
            pair = frozenset((addrs[i], addrs[j]))
            assert (pair in cospent) == (pair in naive), pair


def test_does_not_key_on_an_absent_txid():
    """Synthetic samples carry no txid. Keying on it collapses every transaction onto None,
    which makes every pair of addresses read as co-spent and silently empties the held-out
    positives rather than raising."""
    sample = [(_tx(["a"], ["x"]), None), (_tx(["b"], ["y"]), None)]
    _uf, _n, _p, cospent = build(sample)
    assert frozenset(("a", "b")) not in cospent


def test_membership_is_symmetric_and_ignores_unknown_addresses():
    c = CoSpent()
    c.add(0, ["a", "b"])
    assert frozenset(("a", "b")) in c and frozenset(("b", "a")) in c
    assert frozenset(("a", "zzz")) not in c
    assert frozenset(("zzz", "yyy")) not in c


def test_storage_is_linear_in_inputs_not_quadratic():
    """A 200-input consolidation implies 19 900 pairs; the point of the structure is that it
    stores 200 entries instead."""
    c = CoSpent()
    wide = [f"a{i}" for i in range(200)]
    c.add(0, wide)
    assert len(c._txs) == 200
    assert frozenset(("a0", "a199")) in c

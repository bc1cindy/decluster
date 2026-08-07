"""N-ary provenance intersection.

`ancestry.provenance_link` scores one *pair* of signatures and returns a scalar,
discarding which ancestors were shared. The intersection attack needs the set:
given transactions already attributed to an entity, which coins in a later
transaction descend from them, and how anomalous is that overlap.

The overlap is a candidate *cut*, and only that. It narrows which coins a
hypothesis may invoke; it never asserts that a coin belongs to anyone. A coinjoin
the entity joined shows a share of its inputs coming from the entity's own earlier
transactions, and unrelated rounds show the background rate, so ranking rounds by
that share turns a few hundred inputs into a few dozen candidates to test.

One hop, not a walk: `descended_inputs` tests direct parentage. The multi-hop
candidate-origin sets an intersection attack needs are `ancestry.ancestry_signature`,
which this does not compute and is not a substitute for.
"""


def funding_txids(tx):
    """Txids that funded `tx`, one entry per distinct parent."""
    return {v["txid"] for v in tx.get("vin", []) if "txid" in v}


def descended_inputs(tx, known):
    """Inputs of `tx` spending an output of any tx in `known`.

    Returns `[(index, txid, vout, value)]` in vin order. `value` is None when the
    prevout was not resolved, so callers can tell "no value" from "zero value".
    """
    out = []
    for i, v in enumerate(tx.get("vin", [])):
        if v.get("txid") in known:
            prevout = v.get("prevout") or {}
            out.append((i, v["txid"], v.get("vout"), prevout.get("value")))
    return out


def overlap_share(tx, known):
    """Fraction of `tx`'s inputs that descend from `known`. 0.0 for an empty tx."""
    vin = tx.get("vin", [])
    if not vin:
        return 0.0
    return len(descended_inputs(tx, known)) / len(vin)


def rank_by_overlap(txs, known):
    """Transactions ordered by descending provenance overlap.

    Returns `[(txid, n_descended, n_inputs, share)]`. The point of the ranking is
    the spread: a round the entity joined stands well above the background rate,
    and that gap is what justifies spending search effort on it.
    """
    rows = []
    for tx in txs:
        vin = tx.get("vin", [])
        n = len(descended_inputs(tx, known))
        rows.append((tx.get("txid"), n, len(vin), (n / len(vin)) if vin else 0.0))
    rows.sort(key=lambda r: (-r[3], -r[1]))
    return rows


def candidate_coins(tx, known, anchor_value=None):
    """Coins in `tx` the entity could have registered alongside `anchor_value`.

    The candidates are exactly the provenance-descended inputs, minus one coin
    matching `anchor_value` — the coin already attributed, which is the anchor
    rather than an extra. Returns `[(value, script_type, count)]`, largest first;
    inputs whose prevout value is missing are dropped, since an unvalued coin
    cannot enter an amount hypothesis.

    The script type is carried because a coin's input vsize follows from it, and
    the fee a registration pays follows from that. Reducing a candidate to its
    value alone forces the caller to guess a vsize it was handed.
    """
    coins = []
    for i, _, _, val in descended_inputs(tx, known):
        if val is None:
            continue
        coins.append((val, (tx["vin"][i].get("prevout") or {}).get("scriptpubkey_type")))
    if anchor_value is not None:
        at = next((i for i, c in enumerate(coins) if c[0] == anchor_value), None)
        if at is not None:
            del coins[at]
    counts = {}
    for c in coins:
        counts[c] = counts.get(c, 0) + 1
    return sorted(
        ((v, t, n) for (v, t), n in counts.items()), key=lambda r: -r[0]
    )


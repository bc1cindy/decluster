"""Watch a set of coins for a co-spend the clustering engine should evaluate.

This module decides nothing. A later transaction spending two tracked branches is
the *occasion* for an intersection argument, not the argument itself: co-spending
is the common-input heuristic, and refusing it where the evidence says to is the
whole point of `cluster.cluster_refined`. What is reported here is a candidate to
hand to that engine, never a conclusion.

Three limits make the distinction load-bearing rather than pedantic.

The stop rule wants `COINJOIN_MIN_PARTICIPANTS` on *both* sides, so a large mix is
recognised and the walk halts there — two tracked coins meeting inside one is what
a mix is for, and is not a candidate. But the rule is symmetric and collaborative
transactions need not be: a many-senders/one-receiver payment is short on outputs
however many inputs it has, so 300-in/2-out passes as an ordinary consolidation.
That is the shape where the common-input heuristic pulls hardest and where the
amount channel has least to say, since `subtransaction` re-partitions 2-in/2-out
only. Nothing here decides it either way; the engine scores it, on fingerprint and
topology, with the amount channel silent (PAPER §2, and §9 on generalizing it).

The 2-in/2-out merge PAPER §2 and §6 are built around passes the rule too, being
under the threshold on both sides rather than one, and `shape` on each candidate
makes it visible. That shape is not a verdict
— an ordinary payment with change wears it too — but it is the one the amount
channel can re-partition.

And the walk follows every output of an ordinary spend, having no change
identification, so a branch includes the counterparty's coin as readily as the
owner's; `change_cluster` and `change_special` exist for that and are not wired in
here.

The walk stops where attribution stops being decidable: at an unspent coin, at a
mix, or at the depth limit, reporting which.
"""

COINJOIN_MIN_PARTICIPANTS = 20

UNSPENT = "unspent"
COINJOIN = "coinjoin"
DEPTH = "depth"


def is_coinjoin(tx, min_participants=COINJOIN_MIN_PARTICIPANTS):
    """Many inputs and many outputs — the shape where co-spending stops implying
    common ownership, and so the shape where a forward walk must stop."""
    return (
        len(tx.get("vin", [])) >= min_participants
        and len(tx.get("vout", [])) >= min_participants
    )


def walk_frontier(seeds, fetch_tx, fetch_outspends, max_depth=4, coinjoin=is_coinjoin):
    """Follow each seed forward through ordinary spends only.

    `seeds` are `(txid, vout)` outpoints. Returns `{"frontier": [...],
    "candidates": [...]}`.

    A frontier entry is `{"outpoint", "seed", "depth", "reason"}` — where the walk
    stopped and why. A candidate entry is `{"txid", "seeds", "outpoints", "shape"}`
    for a non-mix transaction spending coins that trace back to two or more
    distinct seeds: a co-spend worth scoring, not a link. `shape` is the spender's
    `(n_in, n_out)`, so a 2-in/2-out spend is visible in the result instead of
    needing another fetch. The shape is not itself a verdict — an ordinary payment
    with change and a two-party collaborative merge wear it equally, and only the
    amounts tell them apart — but it is the shape the amount channel can
    re-partition, and `cluster_refined` runs `subtransaction` on exactly it. It is a
    candidate precisely because the limits in the module docstring mean it can be a
    counterparty coincidence or a collaborative merge as readily as one owner
    consolidating.

    An empty list is the expected result, not a failure: the occasion is an
    external event, and branches that stay unspent or re-enter a mix never
    supply one.
    """
    frontier, candidates = [], []
    # txid -> {seed: [outpoint]} for every tracked coin each tx consumes
    consumers = {}
    shapes = {}   # txid -> (n_in, n_out)
    queue = [(op, op, 0) for op in seeds]
    # Keyed by (coin, seed): two seeds reaching one coin is the signal a
    # candidate is built from, but one seed reaching it twice is just the
    # same branch walked again.
    seen = set()

    while queue:
        outpoint, seed, depth = queue.pop(0)
        if (outpoint, seed) in seen:
            continue
        seen.add((outpoint, seed))
        txid, vout = outpoint
        spends = fetch_outspends(txid)
        if vout >= len(spends) or not spends[vout].get("spent"):
            frontier.append(
                {"outpoint": outpoint, "seed": seed, "depth": depth, "reason": UNSPENT}
            )
            continue
        spender_id = spends[vout]["txid"]
        spender = fetch_tx(spender_id)
        if coinjoin(spender):
            # Not recorded: two tracked coins meeting in a mix is what a mix is
            # for, so it is not even a candidate.
            frontier.append(
                {"outpoint": outpoint, "seed": seed, "depth": depth, "reason": COINJOIN}
            )
            continue
        consumers.setdefault(spender_id, {}).setdefault(seed, []).append(outpoint)
        shapes[spender_id] = (len(spender.get("vin", [])), len(spender.get("vout", [])))
        if depth + 1 > max_depth:
            frontier.append(
                {"outpoint": outpoint, "seed": seed, "depth": depth, "reason": DEPTH}
            )
            continue
        for i in range(len(spender.get("vout", []))):
            queue.append(((spender_id, i), seed, depth + 1))

    for txid, by_seed in consumers.items():
        if len(by_seed) < 2:
            continue
        candidates.append(
            {
                "txid": txid,
                "seeds": sorted(by_seed),
                "outpoints": sorted(op for ops in by_seed.values() for op in ops),
                "shape": shapes[txid],
            }
        )
    candidates.sort(key=lambda c: c["txid"])
    return {"frontier": frontier, "candidates": candidates}


def summarise(result):
    """Counts by stop reason, plus how many co-spend candidates were seen."""
    counts = {}
    for entry in result["frontier"]:
        counts[entry["reason"]] = counts.get(entry["reason"], 0) + 1
    return {"stops": counts, "candidates": len(result["candidates"])}

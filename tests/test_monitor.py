from decluster.monitor import COINJOIN, DEPTH, UNSPENT, is_coinjoin, summarise, walk_frontier


def _chain(txs, spends):
    """txs: {txid: tx}; spends: {txid: [outspend entries]}"""

    def fetch_tx(txid):
        return txs[txid]

    def fetch_outspends(txid):
        return spends.get(txid, [])

    return fetch_tx, fetch_outspends


def _tx(n_in=1, n_out=1):
    return {"vin": [{}] * n_in, "vout": [{}] * n_out}


def _spent(txid):
    return {"spent": True, "txid": txid}


UNSPENT_ENTRY = {"spent": False}


def test_is_coinjoin_needs_both_sides_wide():
    assert is_coinjoin(_tx(20, 20))
    assert not is_coinjoin(_tx(20, 2))
    assert not is_coinjoin(_tx(2, 20))


def test_an_unspent_seed_is_its_own_frontier():
    txs = {"a": _tx()}
    got = walk_frontier([("a", 0)], *_chain(txs, {"a": [UNSPENT_ENTRY]}))
    assert got["frontier"] == [
        {"outpoint": ("a", 0), "seed": ("a", 0), "depth": 0, "reason": UNSPENT}
    ]
    assert got["candidates"] == []


def test_the_walk_stops_where_a_coin_enters_a_coinjoin():
    txs = {"a": _tx(), "cj": _tx(30, 30)}
    got = walk_frontier([("a", 0)], *_chain(txs, {"a": [_spent("cj")]}))
    assert [e["reason"] for e in got["frontier"]] == [COINJOIN]
    assert got["frontier"][0]["depth"] == 0


def test_the_walk_follows_ordinary_spends():
    txs = {"a": _tx(), "b": _tx(1, 2), "c": _tx()}
    spends = {"a": [_spent("b")], "b": [_spent("c"), UNSPENT_ENTRY], "c": [UNSPENT_ENTRY]}
    got = walk_frontier([("a", 0)], *_chain(txs, spends))
    reasons = sorted(e["reason"] for e in got["frontier"])
    assert reasons == [UNSPENT, UNSPENT]
    assert all(e["seed"] == ("a", 0) for e in got["frontier"])


def test_the_depth_limit_is_reported_as_such():
    txs = {"a": _tx(), "b": _tx(), "c": _tx()}
    spends = {"a": [_spent("b")], "b": [_spent("c")], "c": [UNSPENT_ENTRY]}
    got = walk_frontier([("a", 0)], *_chain(txs, spends), max_depth=1)
    assert [e["reason"] for e in got["frontier"]] == [DEPTH]


def test_two_branches_meeting_in_an_ordinary_spend_is_a_candidate():
    # seeds ("a",0) and ("a",1) are both spent by "join"
    txs = {"a": _tx(1, 2), "join": _tx(2, 1)}
    spends = {"a": [_spent("join"), _spent("join")], "join": [UNSPENT_ENTRY]}
    got = walk_frontier([("a", 0), ("a", 1)], *_chain(txs, spends))
    assert len(got["candidates"]) == 1
    assert got["candidates"][0]["txid"] == "join"
    assert got["candidates"][0]["seeds"] == [("a", 0), ("a", 1)]


def test_two_branches_meeting_inside_a_mix_is_not_a_candidate():
    """The stop rule: co-spending in a mix carries no ownership signal at all."""
    txs = {"a": _tx(1, 2), "cj": _tx(30, 30)}
    spends = {"a": [_spent("cj"), _spent("cj")], "cj": [UNSPENT_ENTRY] * 30}
    got = walk_frontier([("a", 0), ("a", 1)], *_chain(txs, spends))
    assert got["candidates"] == []
    assert [e["reason"] for e in got["frontier"]] == [COINJOIN, COINJOIN]


def test_one_seed_spent_twice_into_one_tx_is_not_a_candidate():
    """A candidate needs two distinct seeds, not one seed's own outputs."""
    txs = {"a": _tx(), "b": _tx(1, 2), "join": _tx(2, 1)}
    spends = {
        "a": [_spent("b")],
        "b": [_spent("join"), _spent("join")],
        "join": [UNSPENT_ENTRY],
    }
    got = walk_frontier([("a", 0)], *_chain(txs, spends))
    assert got["candidates"] == []


def test_summarise_counts_stops_and_candidates():
    txs = {"a": _tx(), "cj": _tx(30, 30), "b": _tx()}
    spends = {"a": [_spent("cj")], "b": [UNSPENT_ENTRY]}
    got = walk_frontier([("a", 0), ("b", 0)], *_chain(txs, spends))
    assert summarise(got) == {"stops": {COINJOIN: 1, UNSPENT: 1}, "candidates": 0}


def test_a_candidate_carries_the_spender_shape():
    """A 2-in/2-out merge is the collaborative form where a co-spend is a planted
    link, so it has to be visible in the result rather than inferred later."""
    txs = {
        "s": {"vin": [{}], "vout": [{}, {}]},
        "m": {"vin": [{}, {}], "vout": [{}, {}]},
    }
    spends = {
        "s": [{"spent": True, "txid": "m"}, {"spent": True, "txid": "m"}],
        "m": [{"spent": False}, {"spent": False}],
    }
    out = walk_frontier(
        [("s", 0), ("s", 1)], txs.__getitem__, lambda t: spends.get(t, []), max_depth=2
    )
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["shape"] == (2, 2)


def test_the_walk_does_not_revisit_a_coin_reached_twice_from_one_seed():
    """Two paths converging on one coin is the same branch walked again, not two
    branches; without a visited set it is fetched and reported twice."""
    txs = {
        "s": {"vin": [{}], "vout": [{}]},
        "a": {"vin": [{}], "vout": [{}, {}]},
        "b": {"vin": [{}, {}], "vout": [{}]},
    }
    spends = {
        "s": [{"spent": True, "txid": "a"}],
        "a": [{"spent": True, "txid": "b"}, {"spent": True, "txid": "b"}],
        "b": [{"spent": False}],
    }
    out = walk_frontier(
        [("s", 0)], txs.__getitem__, lambda t: spends.get(t, []), max_depth=4
    )
    assert [e["outpoint"] for e in out["frontier"]] == [("b", 0)]

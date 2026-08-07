from examples.intersection_pipeline import run


def _fixture():
    """One seed tx whose two outputs are later co-spent by an ordinary transaction."""
    txs = {
        "seed": {"vin": [{}], "vout": [{}, {}]},
        "join": {"vin": [{}, {}], "vout": [{}]},
    }
    spends = {
        "seed": [{"spent": True, "txid": "join"}, {"spent": True, "txid": "join"}],
        "join": [{"spent": False}],
    }
    return txs.__getitem__, lambda t: spends.get(t, [])


def test_the_four_channels_chain_end_to_end():
    """monitor -> signatures -> intersect -> engine, with nothing decided in between."""
    get_tx, get_outspends = _fixture()
    sigs = {("seed", 0): ({"red": 0.5, "green": 0.5}, 0), ("seed", 1): ({"red": 0.5, "blue": 0.5}, 0)}
    out = run(
        seeds=[("seed", 0), ("seed", 1)],
        get_tx=get_tx,
        get_outspends=get_outspends,
        signature_of=sigs.__getitem__,
        cluster_fn=lambda nodes, sigs=None: ([{"seed"}], [], []),
    )
    assert len(out["results"]) == 1
    entry = out["results"][0]
    assert entry["candidate"]["txid"] == "join"
    assert [x[0] for x in entry["narrowing"]["shared"]] == ["red"]
    assert entry["narrowing"]["collapsed"] == 1
    assert entry["verdict"]["believed"] is True


def test_the_engine_can_refuse_a_cospend_the_walk_found():
    """The step that separates this from the common-input heuristic."""
    get_tx, get_outspends = _fixture()
    sigs = {("seed", 0): ({"red": 1.0}, 0), ("seed", 1): ({"red": 1.0}, 0)}
    refused = [("seed", "seed", "t", -5.0, 0.0, -5.0)]
    out = run(
        seeds=[("seed", 0), ("seed", 1)],
        get_tx=get_tx,
        get_outspends=get_outspends,
        signature_of=sigs.__getitem__,
        cluster_fn=lambda nodes, sigs=None: ([{"seed"}], refused, []),
    )
    assert out["results"][0]["verdict"]["believed"] is False


def test_a_walk_with_no_cospend_yields_no_results():
    """The expected state: branches unspent or inside mixes."""
    txs = {"seed": {"vin": [{}], "vout": [{}]}, "cj": {"vin": [{}] * 30, "vout": [{}] * 30}}
    spends = {"seed": [{"spent": True, "txid": "cj"}], "cj": [{"spent": False}] * 30}
    out = run(
        seeds=[("seed", 0)],
        get_tx=txs.__getitem__,
        get_outspends=lambda t: spends.get(t, []),
        signature_of=lambda op: ({"red": 1.0}, 0),
        cluster_fn=lambda nodes, sigs=None: ([], [], []),
    )
    assert out["results"] == []
    assert [e["reason"] for e in out["walk"]["frontier"]] == ["coinjoin"]


def test_the_narrowing_is_skipped_when_no_signatures_are_supplied():
    """Each stage is optional; the walk alone is still a useful answer."""
    get_tx, get_outspends = _fixture()
    out = run(
        seeds=[("seed", 0), ("seed", 1)],
        get_tx=get_tx,
        get_outspends=get_outspends,
    )
    entry = out["results"][0]
    assert "narrowing" not in entry
    assert "verdict" not in entry


def test_the_cospend_itself_is_handed_to_the_engine():
    """The engine reads edges out of a node's inputs, so the spending tx has to be
    in the node set. Passing funders alone hands it nothing and every verdict
    comes back refused for the wrong reason."""
    from decluster.intersect import score_candidate

    seen = {}

    def cluster_fn(nodes, sigs=None):
        seen["nodes"] = list(nodes)
        return ([set(nodes)], [], [])

    out = score_candidate(
        {"txid": "join", "outpoints": [("a", 0), ("b", 0)]},
        cluster_fn,
        lambda op: op[0],
    )
    assert seen["nodes"] == ["a", "b", "join"]
    assert out["believed"] is True


def test_the_real_engine_scores_the_candidate(monkeypatch):
    """End to end against cluster_refined itself, not a stand-in."""
    import decluster.cluster as cluster
    from decluster.intersect import score_candidate

    txs = {
        "a": {"txid": "a", "vin": [{"txid": "root"}], "vout": [{"value": 1000}]},
        "b": {"txid": "b", "vin": [{"txid": "root"}], "vout": [{"value": 1000}]},
        "join": {"txid": "join", "vin": [{"txid": "a"}, {"txid": "b"}],
                 "vout": [{"value": 1900}]},
    }
    monkeypatch.setattr(cluster, "fetch_tx", txs.__getitem__)

    class FlatCombiner:
        def score(self, a, b):
            return 0.0        # fingerprint says nothing; the co-spend prior carries

    out = score_candidate(
        {"txid": "join", "outpoints": [("a", 0), ("b", 0)]},
        lambda nodes, sigs=None: cluster.cluster_refined(nodes, FlatCombiner(), amount=False),
        lambda op: op[0],
    )
    assert out["believed"] is True, out
    assert any({"a", "b"} <= set(g) for g in out["groups"])


def test_the_real_engine_can_refuse_on_the_fingerprint(monkeypatch):
    """A negative fingerprint outweighing the co-spend prior splits the pair —
    the case that separates this from the common-input heuristic."""
    import decluster.cluster as cluster
    from decluster.intersect import score_candidate

    txs = {
        "a": {"txid": "a", "vin": [{"txid": "root"}], "vout": [{"value": 1000}]},
        "b": {"txid": "b", "vin": [{"txid": "root"}], "vout": [{"value": 1000}]},
        "join": {"txid": "join", "vin": [{"txid": "a"}, {"txid": "b"}],
                 "vout": [{"value": 1900}]},
    }
    monkeypatch.setattr(cluster, "fetch_tx", txs.__getitem__)

    class HostileCombiner:
        def score(self, a, b):
            return -5.0       # beyond the 2.0-bit co-spend prior

    out = score_candidate(
        {"txid": "join", "outpoints": [("a", 0), ("b", 0)]},
        lambda nodes, sigs=None: cluster.cluster_refined(nodes, HostileCombiner(), amount=False),
        lambda op: op[0],
    )
    assert out["believed"] is False
    assert out["refused_pairs"], "the engine should report the refusal"


def test_default_seeds_reads_the_round_it_is_pointed_at():
    """The seeds are outputs of a known value, taken from the transaction itself."""
    from examples.intersection_pipeline import (
        DENOMINATION, ROUND3, SPINE_TAIL, TAIL_CHANGE, default_seeds,
    )

    txs = {
        ROUND3: {"vout": [{"value": DENOMINATION}, {"value": 1}, {"value": DENOMINATION}]},
        SPINE_TAIL: {"vout": [{"value": 9}, {"value": TAIL_CHANGE}]},
    }
    seeds = default_seeds(txs.__getitem__)
    assert (ROUND3, 0) in seeds and (ROUND3, 2) in seeds
    assert (ROUND3, 1) not in seeds, "only the tracked denomination"


def test_default_signature_of_asks_for_both_halves(monkeypatch):
    """Production must request the truncation count, not only the signature."""
    import decluster.ancestry as ancestry
    from examples.intersection_pipeline import SIGNATURE_DEPTH, default_signature_of

    seen = {}

    def fake(target, depth=6):
        seen["depth"] = depth
        return ({"origin": 1.0}, 3)

    monkeypatch.setattr(ancestry, "ancestry_signature_and_truncation", fake)
    sig, truncated = default_signature_of()(("a", 0))
    assert seen["depth"] == SIGNATURE_DEPTH
    assert sig == {"origin": 1.0} and truncated == 3


def test_default_cluster_fn_turns_the_provenance_channel_on_only_with_signatures(monkeypatch):
    """A channel the caller did not supply must be off, not assumed."""
    import decluster.cluster as cluster
    from examples.intersection_pipeline import default_cluster_fn

    calls = []
    monkeypatch.setattr(
        cluster, "cluster_refined",
        lambda nodes, combiner, **kw: calls.append(kw) or ([set(nodes)], [], []),
    )
    monkeypatch.setattr(
        "decluster.combiner.Combiner.from_library", classmethod(lambda cls, **kw: object())
    )
    fn = default_cluster_fn()
    fn(["a"], None)
    fn(["a"], {"a": {"x": 1.0}})
    assert calls[0]["provenance"] is False and calls[0]["signatures"] is None
    assert calls[1]["provenance"] is True and calls[1]["signatures"] == {"a": {"x": 1.0}}

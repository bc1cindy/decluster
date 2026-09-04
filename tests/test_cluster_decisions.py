import decluster.cluster as cluster


class Scorer:
    def __init__(self, value):
        self.value = value

    def score(self, left, right, explain=False):
        return self.value


def test_decision_log_separates_direct_transitive_and_refused(monkeypatch):
    monkeypatch.setattr(
        cluster,
        "_cospent_pairs",
        lambda nodes: [("a", "b", "t1"), ("a", "c", "t2"), ("b", "c", "t3")],
    )
    monkeypatch.setattr(cluster, "fetch_tx", lambda txid: {"txid": txid})
    scores = {
        frozenset(("a", "b")): 1.0,
        frozenset(("a", "c")): -5.0,
        frozenset(("b", "c")): 1.0,
    }

    class PairScorer:
        def score(self, left, right, explain=False):
            return scores.get(frozenset((left["txid"], right["txid"])), 0.0)

    groups, refused, linked, decisions = cluster.cluster_refined_decisions(
        ["a", "b", "c"], PairScorer(), amount=False, link_above=6.0
    )

    assert refused == []
    assert linked == []
    assert len(groups) == 1
    by_pair = {(decision.left, decision.right): decision for decision in decisions}
    assert by_pair[("a", "b")].status is cluster.PairDecisionStatus.DIRECT_MERGE
    assert by_pair[("a", "c")].status is cluster.PairDecisionStatus.TRANSITIVE_MEMBERSHIP
    assert by_pair[("b", "c")].status is cluster.PairDecisionStatus.DIRECT_MERGE


def test_decision_log_preserves_each_numeric_channel(monkeypatch):
    monkeypatch.setattr(cluster, "_cospent_pairs", lambda nodes: [("a", "b", "spend")])
    monkeypatch.setattr(cluster, "fetch_tx", lambda txid: {"txid": txid})
    monkeypatch.setattr(cluster, "amount_refuse_weight", lambda *args: -1.5)
    signatures = {"a": {"x": 1.0}, "b": {"y": 1.0}}

    _, refused, _, decisions = cluster.cluster_refined_decisions(
        ["a", "b"],
        Scorer(-2.0),
        provenance=True,
        signatures=signatures,
        rarity={"x": 1.0, "y": 1.0},
        prov_refuse_bits=-3.0,
        subsetsum=True,
        _ss_fn=lambda tx, left, right: -4.0,
    )

    assert len(refused) == 1
    decision = decisions[0]
    assert decision.status is cluster.PairDecisionStatus.REFUSED
    assert decision.cospend_prior_bits == 2.0
    assert decision.fingerprint_bits == -2.0
    assert decision.amount_bits == -1.5
    assert decision.provenance_bits == -3.0
    assert decision.subset_sum_bits == -4.0
    assert decision.topology_bits == 0.0
    assert decision.total_bits == -8.5

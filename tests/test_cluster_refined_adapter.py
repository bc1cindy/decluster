import decluster.adaptations.cluster_refined as adapter
from decluster.cluster import ClusterPairDecision, PairDecisionStatus
from decluster.domain import ClusterMerge, MergeRefused


class Scorer:
    def __init__(self, score):
        self.value = score

    def score(self, left, right, explain=False):
        return self.value


def test_adapter_preserves_legacy_result_and_types_refusal(monkeypatch):
    legacy = ([['a'], ['b']], [('a', 'b', 'spend', -5.0, -1.0, -8.0)], [])
    decision = ClusterPairDecision(
        "a", "b", "spend", PairDecisionStatus.REFUSED, 2.0, -5.0, -1.0, -4.0, 0.0, 0.0
    )
    monkeypatch.setattr(
        adapter,
        "cluster_refined_decisions",
        lambda nodes, combiner, **options: legacy + ([decision],),
    )

    report = adapter.cluster_refined_report(['a', 'b'], Scorer(-5.0), amount=False)

    assert report.as_legacy() == legacy
    assert len(report.merge_refusals) == 1
    assert type(report.merge_refusals[0]) is MergeRefused
    assert report.added_links == ()

    attack_report = report.as_attack_report("refusal-fixture")
    assert attack_report.composition is None
    assert [channel.identifier for channel in attack_report.channels] == [
        "cluster_refined",
        "cluster_refined.amount",
        "cluster_refined.cospend_prior",
        "cluster_refined.fingerprint",
        "cluster_refined.topology",
    ]
    assert attack_report.outcomes == report.pair_outcomes


def test_adapter_preserves_legacy_result_and_types_added_link(monkeypatch):
    legacy = ([['a', 'b']], [], [('a', 'b', 6.0)])
    monkeypatch.setattr(
        adapter,
        "cluster_refined_decisions",
        lambda nodes, combiner, **options: legacy + ([],),
    )

    report = adapter.cluster_refined_report(['a', 'b'], Scorer(6.0), link_above=4.0)

    assert report.as_legacy() == legacy
    assert report.merge_refusals == ()
    assert len(report.added_links) == 1
    assert type(report.added_links[0]) is ClusterMerge


def test_adapter_materializes_a_single_pass_node_iterable(monkeypatch):
    observed = []

    def fake(nodes, combiner, **options):
        observed.append(nodes)
        return ([nodes], [], [], [])

    monkeypatch.setattr(adapter, "cluster_refined_decisions", fake)
    nodes = (node for node in ['a', 'b'])

    report = adapter.cluster_refined_report(nodes, Scorer(0.0))

    assert observed == [['a', 'b']]
    assert report.groups == (('a', 'b'),)
    attack_report = report.as_attack_report("no-reported-decisions")
    assert attack_report.channels == ()
    assert attack_report.outcomes[0].observable == "merge refusal or additional fingerprint link"

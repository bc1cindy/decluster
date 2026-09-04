from decluster.adaptations.ancestry import (
    CompleteAncestry,
    TruncatedAncestry,
    ancestry_signature_report,
)


def coinbase_fetch(txid):
    return {"vin": [{"is_coinbase": True}], "vout": [{"value": 10}]}


def binary_fetch(txid):
    if txid in {"left", "right"}:
        return coinbase_fetch(txid)
    return {
        "vin": [
            {"txid": "left", "vout": 0, "prevout": {"value": 5}},
            {"txid": "right", "vout": 0, "prevout": {"value": 5}},
        ],
        "vout": [{"value": 10}],
    }


def test_complete_signature_has_typed_distribution_and_round_trip():
    report = ancestry_signature_report(("target", 0), depth=2, fetch=binary_fetch)

    assert isinstance(report.state, CompleteAncestry)
    distribution, support = report.as_legacy()
    assert distribution == {("left", 0): 0.5, ("right", 0): 0.5}
    assert support.total == 0


def test_node_cap_is_not_conflated_with_oracle_refusal():
    report = ancestry_signature_report(
        ("target", 0), depth=2, fetch=binary_fetch, max_nodes=1
    )

    assert isinstance(report.state, TruncatedAncestry)
    assert report.truncation.node_capped == 2
    assert report.truncation.oracle_refused == 0
    assert report.truncation.total == 2


def test_oracle_refusal_is_preserved_as_its_own_cause():
    report = ancestry_signature_report(
        ("target", 0), depth=2, fetch=binary_fetch, link_oracle=lambda ins, outs: None
    )

    assert isinstance(report.state, TruncatedAncestry)
    assert report.truncation.oracle_refused == 1
    assert report.truncation.node_capped == 0
    assert "does not identify them individually" in report.state.evidence.context.limitations[1]

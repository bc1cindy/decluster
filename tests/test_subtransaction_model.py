"""Model gates for amount-interpretation ranking."""

import pytest

from decluster.subtransaction import (
    AmountDecisionStatus,
    TransactionModel,
    enumerate_amount_interpretations,
    evaluate_amount_model,
    partition_signal,
    rank_amount_interpretations,
)


def _transaction(inputs=(913, 407), outputs=(907, 413)):
    return {
        "txid": "ambiguous-roundness",
        "vin": [
            {"txid": f"input-{index}", "prevout": {"value": value}}
            for index, value in enumerate(inputs)
        ],
        "vout": [{"value": value} for value in outputs],
    }


def test_enumeration_and_ranking_are_separate_operations():
    candidates = enumerate_amount_interpretations(_transaction())
    ranked = rank_amount_interpretations(candidates)

    assert {item.implied_net_transfer for item in candidates} == {6, 500}
    assert ranked[0].implied_net_transfer == 500
    assert set(ranked) == set(candidates)


def test_unknown_model_preserves_candidates_without_directional_output():
    decision = evaluate_amount_model(_transaction(), TransactionModel.UNKNOWN)

    assert decision.status is AmountDecisionStatus.INCONCLUSIVE
    assert decision.ranked
    assert set(decision.ranked) == set(decision.interpretations)
    assert decision.refuse == ()
    assert decision.links == ()


def test_net_settlement_model_cannot_turn_roundness_into_ownership():
    decision = evaluate_amount_model(
        _transaction(), TransactionModel.NET_SETTLEMENT_ALLOWED
    )

    assert decision.status is AmountDecisionStatus.INCONCLUSIVE
    assert decision.refuse == ()
    assert decision.links == ()
    assert "not restricted" in decision.reason


def test_restricted_model_exposes_only_a_directional_hypothesis():
    decision = evaluate_amount_model(
        _transaction(), TransactionModel.RESTRICTED_TWO_PARTY_PAYMENT
    )

    assert decision.status is AmountDecisionStatus.DIRECTIONAL_HYPOTHESIS
    assert decision.ranked[0].implied_net_transfer == 500
    assert decision.refuse
    assert decision.links


def test_legacy_partition_signal_is_an_explicit_restricted_model_adapter():
    signal = partition_signal(_transaction())
    decision = evaluate_amount_model(
        _transaction(), TransactionModel.RESTRICTED_TWO_PARTY_PAYMENT
    )

    assert signal["payment"] == decision.ranked[0].implied_net_transfer
    assert signal["refuse"] == list(decision.refuse)
    assert signal["link"] == list(decision.links)


def test_out_of_scope_shape_has_no_directional_output():
    tx = _transaction(inputs=(10,), outputs=(9,))
    decision = evaluate_amount_model(tx, TransactionModel.RESTRICTED_TWO_PARTY_PAYMENT)

    assert decision.status is AmountDecisionStatus.OUT_OF_SCOPE
    assert decision.refuse == ()
    assert decision.links == ()


def test_model_cannot_be_an_unchecked_string():
    with pytest.raises(TypeError, match="TransactionModel"):
        evaluate_amount_model(_transaction(), "restricted_two_party_payment")

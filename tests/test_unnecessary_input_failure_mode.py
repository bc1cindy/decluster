"""Negative interpretation gates for unnecessary-input evidence."""

import pytest

from decluster.domain import Inconclusive, UnnecessaryInputEvidence
from decluster.failure_modes.unnecessary_input import (
    LatentTransactionForm,
    UnnecessaryInputScenario,
    evaluate,
    observationally_equivalent_example,
)


def test_positive_uih_remains_inconclusive_across_equivalent_worlds():
    scenario = observationally_equivalent_example()
    report = evaluate(scenario)

    evidence = report.channels[0].evidence[0]
    assert isinstance(evidence, UnnecessaryInputEvidence)
    assert evidence.classification == "uih2"
    assert evidence.fee == 100
    assert isinstance(report.outcomes[0], Inconclusive)
    assert report.composition is None


def test_report_emits_no_ownership_or_payjoin_decision():
    report = evaluate(observationally_equivalent_example())

    assert len(report.outcomes) == 1
    assert type(report.outcomes[0]) is Inconclusive
    assert "does not identify PayJoin" in report.limitations[0]
    assert "ownership" in report.limitations[1]


def test_net_settlement_and_unilateral_consolidation_are_both_preserved():
    forms = set(observationally_equivalent_example().possible_forms)

    assert LatentTransactionForm.ORDINARY_CONSOLIDATION in forms
    assert LatentTransactionForm.NET_SETTLEMENT in forms
    assert LatentTransactionForm.TWO_PARTY_PAYJOIN in forms


def test_a_single_asserted_world_cannot_claim_observational_equivalence():
    base = observationally_equivalent_example()

    with pytest.raises(ValueError, match="at least two distinct"):
        UnnecessaryInputScenario(
            base.transaction,
            base.inputs,
            base.outputs,
            (LatentTransactionForm.TWO_PARTY_PAYJOIN,),
        )


def test_duplicate_worlds_do_not_satisfy_the_gate():
    base = observationally_equivalent_example()

    with pytest.raises(ValueError, match="at least two distinct"):
        UnnecessaryInputScenario(
            base.transaction,
            base.inputs,
            base.outputs,
            (
                LatentTransactionForm.NET_SETTLEMENT,
                LatentTransactionForm.NET_SETTLEMENT,
            ),
        )

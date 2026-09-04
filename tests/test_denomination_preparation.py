import pytest

from decluster.domain import Inconclusive, TransactionFingerprintObserved
from decluster.failure_modes.denomination_preparation import (
    DenominationPreparationObservation,
    evaluate,
    fingerprint,
    paired_corpus,
)


def test_preparations_match_the_declared_predecessor_fingerprint():
    preparations, _ = paired_corpus()

    assert all(
        isinstance(evaluate(observation).outcomes[0], TransactionFingerprintObserved)
        for observation in preparations
    )
    assert all(
        dict(fingerprint(observation).features)[
            "exact_denomination_outputs_spent_next"
        ] == 1
        for observation in preparations
    )


def test_arity_matched_controls_do_not_match():
    preparations, controls = paired_corpus()

    assert {(item.input_count, len(item.output_amounts)) for item in preparations} == {
        (item.input_count, len(item.output_amounts)) for item in controls
    }
    assert all(isinstance(evaluate(item).outcomes[0], Inconclusive) for item in controls)


def test_report_does_not_turn_shape_into_ownership():
    report = evaluate(paired_corpus()[0][0])

    assert report.channels[0].identifier == "transaction_shape"
    assert report.composition is None
    assert "not proof" in report.limitations[2]


def test_next_coinjoin_indices_must_reference_an_output():
    observation = paired_corpus()[0][0]

    with pytest.raises(ValueError, match="outside"):
        DenominationPreparationObservation(
            observation.transaction,
            observation.input_count,
            observation.output_amounts,
            frozenset({len(observation.output_amounts)}),
            observation.denomination,
        )


def test_denomination_must_be_positive():
    observation = paired_corpus()[0][0]

    with pytest.raises(ValueError, match="positive"):
        DenominationPreparationObservation(
            observation.transaction,
            observation.input_count,
            observation.output_amounts,
            observation.next_coinjoin_inputs,
            0,
        )

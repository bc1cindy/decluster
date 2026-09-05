"""Receiver-side change read-off over the CTP's many-senders/one-receiver amounts."""

import pytest

from decluster.domain import ConditionalLinksMeasured, Inconclusive
from decluster.failure_modes.ns1r_change_readoff import (
    ReadOffScenario,
    analyze,
    evaluate,
    ns1r_examples,
)


def _amounts(scenario, candidates):
    return {name: sorted(scenario.outputs[index] for index in group) for name, group in candidates}


def _ns1r():
    return ns1r_examples()[0]


def _control():
    return ns1r_examples()[1]


def test_per_sender_readoff_is_locally_ambiguous():
    scenario = _ns1r()

    local = _amounts(scenario, analyze(scenario).local_candidates)

    assert local == {"Alice": [30, 30], "Bob": [20, 30, 30], "Carol": [20]}


def test_propagation_leaves_one_reading_of_every_sender_change():
    scenario = _ns1r()
    analysis = analyze(scenario)

    assert _amounts(scenario, analysis.feasible_candidates) == {
        "Alice": [30, 30],
        "Bob": [30, 30],
        "Carol": [20],
    }
    assert analysis.readings == (
        (("Alice", 50, 30), ("Bob", 60, 30), ("Carol", 90, 20)),
    )


def test_the_residual_ambiguity_is_coin_identity_not_amount():
    analysis = analyze(_ns1r())

    assert len(analysis.matchings) == 2
    assert len(analysis.readings) == 1
    assert analysis.unanimous_links == ((3, 3),)


def test_a_single_sender_readoff_reduces_to_two_party_elimination():
    scenario = ReadOffScenario.from_payments(
        "two-party", (90, 60), (110, 40), 1, 0, {"Alice": 50}
    )

    assert analyze(scenario).readings == ((("Alice", 90, 40),),)


def test_evenly_spaced_amounts_keep_several_readings():
    scenario = _control()
    analysis = analyze(scenario)

    assert len(analysis.readings) == 2
    assert analysis.unanimous_links == ()
    assert {
        change for reading in analysis.readings for name, _, change in reading if name == "Bob"
    } == {20, 30}


def test_report_records_propagation_and_abstains_when_readings_disagree():
    decided = evaluate(_ns1r())
    undecided = evaluate(_control())

    assert [channel.identifier for channel in decided.channels] == [
        "per_sender_remainder",
        "matching_propagation",
    ]
    assert [type(outcome) for outcome in decided.outcomes] == [ConditionalLinksMeasured]
    assert Inconclusive in {type(outcome) for outcome in undecided.outcomes}


def test_report_does_not_claim_ownership():
    report = evaluate(_ns1r())

    assert any("does not attribute ownership" in item for item in report.limitations)
    assert any("declared knowledge" in item for item in report.limitations)


def test_receiver_block_never_conserves_value_so_exact_block_mappings_do_not_apply():
    scenario = _ns1r()

    assert scenario.outputs[scenario.receiver_output] != scenario.inputs[scenario.receiver_input]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"outputs": (160, 30, 30, 30)},
        {"receiver_output": 1},
        {"payments": (("Alice", 20), ("Alice", 30), ("Carol", 70))},
        {"payments": (("Alice", 20), ("Bob", 30))},
    ],
)
def test_scenario_rejects_models_the_readoff_cannot_state(kwargs):
    fields = {
        "identifier": "invalid",
        "inputs": (40, 50, 60, 90),
        "outputs": (160, 30, 30, 20),
        "receiver_input": 0,
        "receiver_output": 0,
        "payments": (("Alice", 20), ("Bob", 30), ("Carol", 70)),
    }
    fields.update(kwargs)

    with pytest.raises(ValueError):
        ReadOffScenario(**fields)

"""Executable observer-knowledge matrix for CTP collaborative forms."""

from decluster.failure_modes.collaborative_forms import (
    TWO_PARTY_OBSERVATION,
    CollaborativeForm,
    Observer,
    form_matrix,
    knowledge,
)
from decluster.failure_modes.ns1r_change_readoff import ReadOffScenario, analyze

TWO_PARTY_FORMS = (
    CollaborativeForm.ORDINARY_TWO_INPUT,
    CollaborativeForm.P2EP,
    CollaborativeForm.BIP79,
    CollaborativeForm.BIP78,
    CollaborativeForm.BIP77,
)


def _by_form():
    return {row.form: row for row in form_matrix()}


def _read_off(form, receiver_input, receiver_output, payments):
    row = _by_form()[form]
    return analyze(
        ReadOffScenario.from_payments(
            form.value,
            row.observation.inputs,
            row.observation.outputs,
            receiver_input,
            receiver_output,
            payments,
        )
    )


def test_all_declared_ctp_forms_are_present_once():
    rows = form_matrix()

    assert len(rows) == len(CollaborativeForm)
    assert {row.form for row in rows} == set(CollaborativeForm)


def test_two_party_protocols_can_share_one_onchain_observation_with_ordinary_spend():
    rows = _by_form()

    assert {rows[form].observation for form in TWO_PARTY_FORMS} == {TWO_PARTY_OBSERVATION}
    assert len({rows[form].transport for form in TWO_PARTY_FORMS}) == len(TWO_PARTY_FORMS)


def test_external_observer_sees_the_same_thing_in_every_two_party_form():
    rows = _by_form()

    external = {knowledge(rows[form], Observer.EXTERNAL) for form in TWO_PARTY_FORMS}
    counterparty = {knowledge(rows[form], Observer.COUNTERPARTY) for form in TWO_PARTY_FORMS}

    assert len(external) == 1
    assert len(counterparty) == 2
    assert knowledge(rows[CollaborativeForm.ORDINARY_TWO_INPUT], Observer.COUNTERPARTY) == ()


def test_two_party_counterparty_can_eliminate_own_coins():
    analysis = _read_off(CollaborativeForm.BIP78, 1, 0, {"sender": 50})

    assert analysis.readings == ((("sender", 90, 40),),)
    assert analysis.unanimous_links == ((0, 1),)


def test_ns1r_receiver_knowledge_does_not_become_input_attribution():
    analysis = _read_off(
        CollaborativeForm.NS1R, 0, 0, {"Alice": 20, "Bob": 30, "Carol": 70}
    )
    local = dict(analysis.local_candidates)

    assert len(local["Alice"]) > 1 and len(local["Bob"]) > 1
    assert len(analysis.matchings) > 1
    assert analysis.readings == (
        (("Alice", 50, 30), ("Bob", 60, 30), ("Carol", 90, 20)),
    )


def test_nsnr_row_keeps_six_parties_with_one_coin_per_party_on_each_side():
    row = _by_form()[CollaborativeForm.NSNR]

    assert row.participants == 6
    assert len(row.observation.inputs) == len(row.observation.outputs) == row.participants
    assert sum(row.observation.inputs) == sum(row.observation.outputs)


def test_net_settlement_row_leaves_the_participant_count_latent():
    row = _by_form()[CollaborativeForm.NET_SETTLEMENT]

    assert row.participants is None
    assert len(row.observation.inputs) == len(row.observation.outputs)
    assert sum(row.observation.inputs) == sum(row.observation.outputs)


def test_matrix_never_places_transport_in_external_onchain_knowledge():
    for row in form_matrix():
        assert row.transport not in knowledge(row, Observer.EXTERNAL)

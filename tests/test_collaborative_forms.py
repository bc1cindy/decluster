"""Executable observer-knowledge matrix for CTP collaborative forms."""

from decluster.failure_modes.collaborative_forms import (
    TWO_PARTY_OBSERVATION,
    CollaborativeForm,
    Observer,
    form_matrix,
    knowledge,
)


def _by_form():
    return {row.form: row for row in form_matrix()}


def test_all_declared_ctp_forms_are_present_once():
    rows = form_matrix()

    assert len(rows) == len(CollaborativeForm)
    assert {row.form for row in rows} == set(CollaborativeForm)


def test_two_party_protocols_can_share_one_onchain_observation_with_ordinary_spend():
    rows = _by_form()
    forms = (
        CollaborativeForm.ORDINARY_TWO_INPUT,
        CollaborativeForm.P2EP,
        CollaborativeForm.BIP79,
        CollaborativeForm.BIP78,
        CollaborativeForm.BIP77,
    )

    assert {rows[form].observation for form in forms} == {TWO_PARTY_OBSERVATION}
    assert len({rows[form].transport for form in forms}) == len(forms)


def test_external_observer_does_not_receive_protocol_allocation_or_payment():
    rows = _by_form()

    for form in (
        CollaborativeForm.P2EP,
        CollaborativeForm.BIP79,
        CollaborativeForm.BIP78,
        CollaborativeForm.BIP77,
    ):
        observed = knowledge(rows[form], Observer.EXTERNAL)
        assert "participant allocation is not observed" in observed
        assert "payment amount is not observed" in observed


def test_two_party_counterparty_can_eliminate_own_coins():
    row = _by_form()[CollaborativeForm.BIP78]

    assert "own inputs and outputs" in knowledge(row, Observer.COUNTERPARTY)
    assert any("only other party" in item for item in knowledge(row, Observer.COUNTERPARTY))


def test_ns1r_receiver_knowledge_does_not_become_input_attribution():
    row = _by_form()[CollaborativeForm.NS1R]
    known = knowledge(row, Observer.COUNTERPARTY)

    assert any("knows each negotiated payment" in item for item in known)
    assert any("may not know which input" in item for item in known)


def test_nsnr_preserves_other_pairings_and_amount_signal_limit():
    row = _by_form()[CollaborativeForm.NSNR]

    assert "other pairings remain latent" in knowledge(row, Observer.COUNTERPARTY)
    assert any("amount-based" in limitation for limitation in row.limitations)


def test_net_settlement_exposes_net_balances_not_gross_obligations():
    row = _by_form()[CollaborativeForm.NET_SETTLEMENT]

    assert "net on-chain balances" in knowledge(row, Observer.EXTERNAL)
    assert any("gross obligations remain latent" in item for item in knowledge(row, Observer.COUNTERPARTY))
    assert any("cycles" in limitation for limitation in row.limitations)


def test_matrix_never_places_transport_in_external_onchain_knowledge():
    for row in form_matrix():
        assert row.transport not in knowledge(row, Observer.EXTERNAL)

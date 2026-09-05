from decluster.experiments.collaborative_forms import (
    build_artifact,
    render_markdown,
    verify_artifact,
)


def test_artifact_preserves_observer_boundaries_and_onchain_equivalence():
    artifact = build_artifact()
    rows = {row["form"]: row for row in artifact["forms"]}
    equivalent = artifact["two_party_onchain_equivalence"]

    assert equivalent["forms"] == [
        "ordinary_two_input",
        "p2ep",
        "bip79_bustapay",
        "bip78_sync_payjoin",
        "bip77_async_payjoin",
    ]
    assert equivalent["observation"] == {"inputs_sat": [90, 60], "outputs_sat": [110, 40]}
    assert all(
        "participant allocation is not observed" in rows[form]["external_onchain_knowledge"]
        for form in equivalent["forms"][1:]
    )
    assert any(
        "only other party" in item
        for item in rows["bip78_sync_payjoin"]["counterparty_knowledge"]
    )


def test_artifact_keeps_multiparty_limits_explicit():
    rows = {row["form"]: row for row in build_artifact()["forms"]}

    assert any("may not know which input" in item for item in rows["many_senders_one_receiver"]["counterparty_knowledge"])
    assert any("amount-based" in item for item in rows["many_senders_many_receivers"]["limitations"])
    assert any("cycles" in item for item in rows["net_settlement_with_cycles"]["limitations"])


def test_artifact_and_markdown_are_exactly_recomputable():
    artifact = build_artifact()
    assert verify_artifact(artifact) == artifact
    markdown = render_markdown(artifact)
    assert "does not identify which protocol form occurred" in markdown
    assert "not ownership attribution" in markdown

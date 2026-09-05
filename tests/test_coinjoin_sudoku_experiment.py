from decluster.experiments.coinjoin_sudoku import (
    build_artifact,
    render_markdown,
    verify_artifact,
)


def test_artifact_reproduces_only_the_nominal_primary_source_controls():
    artifact = build_artifact()
    assert artifact["advisory_group_examples"] == {
        "valid_2_plus_3_to_1_plus_4": 1,
        "invalid_2_plus_3_to_1_plus_2": 0,
    }
    matrix = artifact["sx_symmetric_control"]["local_uniform_real_output_link_probabilities"]
    assert all(abs(value - 1 / 3) < 1e-12 for row in matrix for value in row)
    assert artifact["sx_symmetric_control"]["selected_indexed_groupings"] == 36
    assert artifact["sx_symmetric_control"]["selected_groupings_collapsing_fee_permutations"] == 6
    assert artifact["sharedcoin_historical_target"]["status"] == "not_reproduced"


def test_artifact_verifies_against_fresh_execution():
    assert verify_artifact(build_artifact()) == build_artifact()


def test_markdown_refuses_historical_parity_and_ownership_claims():
    markdown = render_markdown(build_artifact())
    assert "does not claim code parity" in markdown
    assert "**not reproduced**" in markdown
    assert "not ownership attribution" in markdown

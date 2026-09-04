from decluster.experiments.deterministic_partition import (
    build_artifact,
    render_markdown,
    verify_artifact,
)


def test_artifact_contrasts_forced_and_underdetermined_examples():
    artifact = build_artifact()
    assert artifact["forced_partition"]["non_derived_mappings"] == 1
    assert len(artifact["forced_partition"]["unanimous_links"]) == 4
    assert artifact["underdetermined_control"]["non_derived_mappings"] == 3
    assert artifact["underdetermined_control"]["unanimous_links"] == []


def test_artifact_verifies_against_fresh_execution():
    assert verify_artifact(build_artifact()) == build_artifact()


def test_markdown_states_the_model_condition():
    markdown = render_markdown(build_artifact())
    assert "| forced partition | 1 | 4 |" in markdown
    assert "conditional on exact per-block conservation" in markdown

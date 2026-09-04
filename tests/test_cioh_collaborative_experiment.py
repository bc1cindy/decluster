from decluster.experiments.cioh_collaborative import (
    build_artifact,
    render_markdown,
    verify_artifact,
)


def test_artifact_separates_collaborative_fixture_from_control():
    artifact = build_artifact()
    assert artifact["collaborative"] == {
        "inputs": 2,
        "predicted_merges": 1,
        "reference_conflicts": 1,
    }
    assert artifact["same_owner_control"]["reference_conflicts"] == 0


def test_artifact_verifies_against_fresh_execution():
    assert verify_artifact(build_artifact()) == build_artifact()


def test_markdown_is_derived_from_artifact():
    markdown = render_markdown(build_artifact())
    assert "| collaborative | 2 | 1 | 1 |" in markdown
    assert "infer real ownership" in markdown

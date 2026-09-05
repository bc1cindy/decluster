"""Canonical executable-coverage contract for N-S 2011."""

import json

import pytest

from decluster.baselines.ns_link_prediction_2011 import PipelineComponent
from decluster.experiments import ns_link_prediction_coverage as experiment


def test_artifact_covers_every_declared_component_once():
    artifact = experiment.build_artifact()
    rows = artifact["components"]

    assert len(rows) == len(PipelineComponent)
    assert {row["component"] for row in rows} == {
        component.value for component in PipelineComponent
    }
    assert artifact["end_to_end_reproduced"] is False
    assert artifact["composition"] is None


def test_every_unavailable_component_has_an_exercised_refusal():
    artifact = experiment.build_artifact()
    unavailable = {
        row["component"] for row in artifact["components"] if row["status"] != "implemented"
    }

    assert set(artifact["refusal_controls"]) == unavailable
    assert all("unavailable" in message for message in artifact["refusal_controls"].values())
    assert artifact["implemented_gate"]["accepted"] is True


def test_verifier_recomputes_coverage_and_refusals():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["end_to_end_reproduced"] = True

    with pytest.raises(experiment.VerificationError, match="fresh coverage"):
        experiment.verify_artifact(changed)


def test_cli_reproduces_and_verifies_json_and_markdown(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"

    assert experiment.main(
        ["reproduce", "--artifact", str(artifact), "--markdown", str(markdown)]
    ) == 0
    assert experiment.main(
        ["verify", "--artifact", str(artifact), "--markdown", str(markdown)]
    ) == 0

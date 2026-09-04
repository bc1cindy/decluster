import json

import pytest

from decluster.experiments import pseudonym_graph_contract as experiment


def test_artifact_preserves_the_representation_invariants():
    artifact = experiment.build_artifact()
    edges = {(edge["source"], edge["target"]): edge for edge in artifact["edges"]}

    assert artifact["vertices"] == ["cluster-a", "cluster-x", "z"]
    assert edges[("cluster-a", "cluster-x")]["transfers"] == 3
    assert edges[("cluster-a", "cluster-x")]["value"] == 600
    assert edges[("cluster-x", "cluster-a")]["transfers"] == 1
    assert artifact["self_transfers"] == {"cluster-a": 1}
    assert artifact["composition"] is None


def test_verifier_recomputes_contraction():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["edges"][0]["transfers"] += 1

    with pytest.raises(experiment.VerificationError, match="fresh contraction"):
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

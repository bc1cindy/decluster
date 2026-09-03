import json

import pytest

from decluster.experiments import exact_oracle_audit as experiment
from decluster.result_artifacts import canonical_json_bytes


pytest.importorskip("dss")


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact(max_coins=6)


def test_artifact_is_deterministic_and_self_describing(artifact):
    assert canonical_json_bytes(artifact) == canonical_json_bytes(
        experiment.build_artifact(max_coins=6)
    )
    assert artifact["experiment"] == experiment.EXPERIMENT_ID
    assert artifact["summary"]["family_size"] == artifact["report"]["family"]["size"]
    assert artifact["parameters"]["max_coins"] == 6
    assert len(artifact["dependencies"]["dss_revision"]) == 40


def test_publishable_artifact_requires_an_identified_dss_build(monkeypatch):
    import dss

    def unidentified():
        raise RuntimeError("missing revision")

    monkeypatch.setattr(dss, "require_build_revision", unidentified)
    with pytest.raises(experiment.VerificationError, match="embedded Git revision"):
        experiment.build_artifact(max_coins=6)


def test_verifier_recomputes_the_experiment(artifact):
    assert experiment.verify_artifact(artifact) == artifact
    changed = json.loads(json.dumps(artifact))
    changed["summary"]["family_size"] += 1
    with pytest.raises(experiment.VerificationError, match="differs from a fresh"):
        experiment.verify_artifact(changed)


def test_verifier_rejects_parameter_drift_before_computation(artifact):
    changed = json.loads(json.dumps(artifact))
    changed["parameters"]["alphabet"] = [1, 2]
    with pytest.raises(experiment.VerificationError, match="unsupported parameter alphabet"):
        experiment.verify_artifact(changed)


def test_cli_round_trip_and_renderer(tmp_path):
    artifact_path = tmp_path / "audit.json"
    markdown_path = tmp_path / "audit.md"
    assert experiment.main(["run", "--output", str(artifact_path), "--max-coins", "6"]) == 0
    assert experiment.main(["verify", "--artifact", str(artifact_path)]) == 0
    assert experiment.main([
        "render", "--artifact", str(artifact_path), "--output", str(markdown_path),
    ]) == 0
    markdown = markdown_path.read_text()
    assert "Generated from the canonical experiment artifact" in markdown
    assert f"| transactions | {json.loads(artifact_path.read_text())['summary']['family_size']} |" in markdown


def test_reproduce_and_verify_cover_artifact_and_markdown(tmp_path):
    artifact_path = tmp_path / "results" / "audit.json"
    markdown_path = tmp_path / "results" / "audit.md"
    assert experiment.main([
        "reproduce", "--artifact", str(artifact_path), "--markdown", str(markdown_path),
        "--max-coins", "6",
    ]) == 0
    assert experiment.main([
        "verify", "--artifact", str(artifact_path), "--markdown", str(markdown_path),
    ]) == 0
    markdown_path.write_text(markdown_path.read_text() + "changed\n")
    with pytest.raises(experiment.VerificationError, match="Markdown differs"):
        experiment.main([
            "verify", "--artifact", str(artifact_path), "--markdown", str(markdown_path),
        ])

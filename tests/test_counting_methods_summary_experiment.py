import json

import pytest

from decluster.experiments import counting_methods_summary as experiment


def test_summary_is_composition_and_records_exclusions():
    artifact = experiment.build_artifact()
    excluded = {row["measurement"] for row in artifact["excluded_historical_measurements"]}
    assert excluded == {
        "wall-clock benchmarks",
        "seven L candidates over 18 synthetic instances",
        "obsolete router shares",
    }
    assert artifact["components"]["router"]["sha256"]
    assert artifact["components"]["fee_sensitivity"]["sha256"]


def test_component_digest_is_enforced(tmp_path):
    paths = {name: specification[0] for name, specification in experiment.COMPONENTS.items()}
    changed = json.loads(open(paths["router"], encoding="utf-8").read())
    changed["report"]["population"]["multi_input_transactions"] += 1
    replacement = tmp_path / "changed.json"
    replacement.write_text(json.dumps(changed), encoding="utf-8")
    paths["router"] = replacement
    with pytest.raises(experiment.VerificationError, match="SHA-256"):
        experiment.build_artifact(paths)


def test_artifact_round_trip(tmp_path):
    artifact = tmp_path / "result.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown)
    ]) == 0
    assert experiment.main([
        "verify", "--artifact", str(artifact), "--markdown", str(markdown)
    ]) == 0

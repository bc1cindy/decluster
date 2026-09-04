import json

import pytest

from decluster.experiments import amount_channel_summary as experiment


def test_summary_is_derived_from_all_pinned_components():
    artifact = experiment.build_artifact()

    assert set(artifact["report"]["components"]) == set(experiment.COMPONENTS)
    assert artifact["report"]["per_coin_candidates"]["transaction_gated"]["candidates"]["total"] == 102
    assert artifact["report"]["mapping_family"]["outcomes"]["answered"] == 223
    assert artifact["report"]["pairwise_family"]["restricted_family_rows"]["singleton_support"] == 367


def test_component_digest_drift_is_rejected(tmp_path):
    path = tmp_path / "changed.json"
    path.write_text(json.dumps({"experiment": "amount-local-channels-v1"}), encoding="utf-8")
    with pytest.raises(experiment.VerificationError, match="SHA-256"):
        experiment._load_component(
            path, "amount-local-channels-v1", experiment.COMPONENTS["local"][2]
        )


def test_verifier_rejects_changed_composition(monkeypatch):
    artifact = {"schema_version": 1, "experiment": experiment.EXPERIMENT_ID, "value": 2}
    monkeypatch.setattr(experiment, "build_artifact", lambda _paths: {**artifact, "value": 1})
    with pytest.raises(experiment.VerificationError, match="component composition"):
        experiment.verify_artifact(artifact)

import json

import pytest

from decluster.experiments import fingerprint_catalog_axes as experiment


def _rows(artifact):
    return {row["configuration"]: row for row in artifact["measurement"]["rows"]}


def test_axis_ablation_uses_one_pair_population_and_preserves_non_additivity():
    artifact = experiment.build_artifact()
    rows = _rows(artifact)
    assert artifact["measurement"]["positive_pair_draws"] == 4000
    assert artifact["measurement"]["negative_pair_draws"] == 4000
    assert rows["plus_output_count"]["auc_delta_from_library"] < 0
    assert rows["plus_segwit_serialization"]["auc_delta_from_library"] > 0
    assert rows["plus_both"]["auc"] < rows["plus_segwit_serialization"]["auc"]


def test_observed_deltas_are_pinned_without_claiming_historical_cache_reproduction():
    rows = _rows(experiment.build_artifact())
    assert rows["plus_output_count"]["auc_delta_from_library"] == pytest.approx(-0.000725)
    assert rows["plus_segwit_serialization"]["auc_delta_from_library"] == pytest.approx(0.0026)
    assert rows["plus_both"]["auc_delta_from_library"] == pytest.approx(0.002125)


def test_duplicate_transaction_ids_are_refused(tmp_path):
    path = tmp_path / "duplicate.json"
    transaction = {"txid": "same", "vin": [], "vout": []}
    path.write_text(json.dumps([transaction, transaction]), encoding="utf-8")
    with pytest.raises(experiment.VerificationError, match="unique"):
        experiment.build_artifact(path)


def test_the_stored_artifact_still_equals_a_fresh_execution():
    """The pinned deltas above say what the numbers mean; this says nothing else moved."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dataset = str(root / "tests" / "fixtures" / "fingerprint_blkcache_sample.json")
    artifact = root / "results/artifacts/fingerprint-catalog-axes-v1.json"
    markdown = root / "results/generated/fingerprint-catalog-axes-v1.md"
    assert experiment.main(["--dataset", dataset, "verify",
                            "--artifact", str(artifact), "--markdown", str(markdown)]) == 0

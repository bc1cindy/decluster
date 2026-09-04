import json
from pathlib import Path

import pytest

from decluster.experiments import ns_bitcoin as experiment


ROOT = Path(__file__).resolve().parents[1]


def test_artifact_preserves_corpus_and_attack_limitations(monkeypatch):
    monkeypatch.setattr(
        experiment.legacy,
        "build_report",
        lambda _args: {"views": {"left": {}, "right": {}}, "runs": []},
    )
    artifact = experiment.build_artifact("left.gz", "right.gz")

    assert artifact["experiment"] == "ns-bitcoin-v1"
    assert "independent gradeable seeds" in artifact["limitations"][0]
    assert "Twitter, Flickr, or LiveJournal" in artifact["limitations"][4]


def test_verifier_rejects_a_changed_measurement(monkeypatch):
    expected = {
        "schema_version": 1,
        "experiment": experiment.EXPERIMENT_ID,
        "corpus": "adjacent public Bitcoin block windows",
        "report": {"value": 1},
        "limitations": [
            "no independent gradeable seeds were found in these windows",
            "the measured sweep uses seeds sampled from withheld correspondence",
            "operational precision is approximately one percent",
            "the observation windows are not representative of the whole chain",
            "this does not reproduce the Twitter, Flickr, or LiveJournal experiments",
        ],
    }
    monkeypatch.setattr(experiment, "build_artifact", lambda *_args: expected)
    changed = json.loads(json.dumps(expected))
    changed["report"]["value"] = 2

    with pytest.raises(experiment.VerificationError, match="fresh experiment"):
        experiment.verify_artifact(changed)


def test_canonical_report_preserves_historical_observation_population(monkeypatch):
    historical = json.loads((ROOT / "results" / "ns-bitcoin.json").read_text())
    report = {
        "views": historical["views"],
        "withheld_correspondence": historical["withheld_correspondence"],
        "independent_entity_seeds": historical["independent_entity_seeds"],
        "runs": [],
    }
    report["views"]["left"]["path"] = experiment.LEFT
    report["views"]["right"]["path"] = experiment.RIGHT
    monkeypatch.setattr(experiment.legacy, "build_report", lambda _args: report)

    measured = experiment.build_artifact()["report"]
    assert measured["views"]["left"]["transactions"] == 133576
    assert measured["views"]["right"]["transactions"] == 157724
    assert measured["withheld_correspondence"]["vertices"] == 2599
    assert measured["independent_entity_seeds"]["found"] == 0

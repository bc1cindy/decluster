"""What the run may and may not claim about a calibration whose population is gone."""
import json
from pathlib import Path

import pytest

from decluster import library
from decluster.experiments import library_calibration as experiment

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = str(ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz")


@pytest.fixture(scope="module")
def artifact():
    return experiment.build_artifact(SNAPSHOT)


def test_reproduce_then_verify(tmp_path):
    art, markdown = tmp_path / "a.json", tmp_path / "a.md"
    argv = ["--snapshot", SNAPSHOT]
    assert experiment.main(argv + ["reproduce", "--artifact", str(art), "--markdown", str(markdown)]) == 0
    assert experiment.main(argv + ["verify", "--artifact", str(art), "--markdown", str(markdown)]) == 0


def test_every_catalogued_axis_is_walked(artifact):
    assert {row["axis"] for row in artifact["measurement"]["axes"]} == {
        entry["axis"] for entry in library.AXES
    }


def test_a_value_the_cache_never_shows_is_counted_not_estimated(artifact):
    absent = [row for axis in artifact["measurement"]["axes"] for row in axis["values"]
              if row["observations"] == 0]
    assert absent, "the comparison is only interesting while something is uncomparable"
    for row in absent:
        assert row["measured_bits"] is None and "divergence" not in row


def test_an_axis_with_nothing_to_compare_reports_no_divergence(artifact):
    empty = [axis for axis in artifact["measurement"]["axes"]
             if axis["values_the_cache_shows"] == 0]
    for axis in empty:
        assert axis["mean_divergence_bits"] is None and axis["max_divergence_bits"] is None


def test_abstentions_are_kept_out_of_the_scored_population(artifact):
    for axis in artifact["measurement"]["axes"]:
        observed = sum(row["observations"] for row in axis["values"])
        assert observed <= axis["scored_transactions"]


def test_the_divergence_is_reported_in_bits_not_hidden_in_an_average(artifact):
    measured = artifact["measurement"]
    assert measured["largest_divergence"][1] > measured["mean_divergence_bits"]


def test_a_tampered_artifact_is_refused(artifact):
    stored = json.loads(json.dumps(artifact))
    stored["measurement"]["axes"][0]["values"][0]["published_bits"] += 1.0
    with pytest.raises(experiment.VerificationError):
        experiment.verify_artifact(stored, SNAPSHOT)

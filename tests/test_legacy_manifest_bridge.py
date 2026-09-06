"""The legacy `results/manifests/` invariants, checked against the canonical run artifacts.

`check_manifest` compares a recorded invariant only when a caller recomputes it, and no caller
does, so all six manifests report `identity-only`: the digest matches and not one number is
compared. Every one of the six now has a canonical run whose artifact carries the same
measurements, which makes the comparison free wherever the two record a value the same way.

Two of the six record every invariant exactly as the artifact does and are bridged here. The other
four aggregate or round — a list of per-fixture values against the per-fixture records, `0.467344`
against `0.46734397677793904` — so bridging them needs an extractor written per document. They are
named in `NEEDS_AN_EXTRACTOR` rather than left to look bridged, and the test fails if that set
grows.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# document stem -> the canonical run whose artifact measures the same thing
BRIDGED = {
    "RESULTS-boltzmann-fee-audit": "boltzmann-fee-audit-v1",
    "RESULTS-candidate-set-intersection": "candidate-set-intersection-v1",
}

NEEDS_AN_EXTRACTOR = {
    "RESULTS-fs-ablation": "six invariants are not carried by the artifact at all",
    "RESULTS-fs-temporal": "six invariants are not carried by the artifact at all",
    "RESULTS-link-prediction": "per-fixture lists against per-fixture records, and a count against a list",
    "RESULTS-ns-bitcoin": "a rounded edge overlap, and a seed count against the object that holds it",
}


def values_by_key(value, found=None):
    """Every value in the artifact, indexed by the key that holds it."""
    found = {} if found is None else found
    if isinstance(value, dict):
        for key, item in value.items():
            found.setdefault(key, []).append(item)
            values_by_key(item, found)
    elif isinstance(value, list):
        for item in value:
            values_by_key(item, found)
    return found


def invariants(document):
    return json.loads((ROOT / "results" / "manifests" / f"{document}.json").read_text())["invariants"]


def artifact(run):
    return json.loads((ROOT / "results" / "artifacts" / f"{run}.json").read_text())


@pytest.mark.parametrize("document,run", sorted(BRIDGED.items()))
def test_every_recorded_invariant_matches_the_canonical_artifact(document, run):
    carried = values_by_key(artifact(run))
    disagreeing = []
    for name, recorded in invariants(document).items():
        assert name in carried, f"{document}: {run} no longer carries {name}"
        if recorded not in carried[name]:
            disagreeing.append(f"{name}: manifest {recorded!r}, artifact {carried[name]!r}")
    assert not disagreeing, f"{document} disagrees with {run}:\n  " + "\n  ".join(disagreeing)


def test_no_further_document_has_quietly_stopped_being_bridgeable():
    manifests = {p.stem for p in (ROOT / "results" / "manifests").glob("*.json")}
    assert manifests == set(BRIDGED) | set(NEEDS_AN_EXTRACTOR), (
        f"unaccounted legacy manifests: {sorted(manifests - set(BRIDGED) - set(NEEDS_AN_EXTRACTOR))}"
    )


@pytest.mark.parametrize("document", sorted(NEEDS_AN_EXTRACTOR))
def test_a_document_that_needs_an_extractor_still_needs_one(document):
    """If a document becomes exactly comparable, move it to BRIDGED rather than leaving it excused."""
    run = {"RESULTS-fs-ablation": "fs-ablation-v1", "RESULTS-fs-temporal": "fs-temporal-v1",
           "RESULTS-link-prediction": "link-prediction-v1", "RESULTS-ns-bitcoin": "ns-bitcoin-v1"}[document]
    carried = values_by_key(artifact(run))
    exact = all(name in carried and recorded in carried[name]
                for name, recorded in invariants(document).items())
    assert not exact, f"{document} now matches {run} exactly; move it to BRIDGED"

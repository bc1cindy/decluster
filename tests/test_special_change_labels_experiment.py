"""Change labels that do not read co-spend, taken again on data a reader has.

The figures this replaces came from downloads outside the repository. What the committed cache
supports is the offline half, and the half it does not support is asserted to stay absent: the
onward-spend arm needs a labelled transaction's outputs to be spent inside the same data, and the
count of those is small enough that a rate computed from them would be a number, not a measurement.

The agreement between address reuse and type match is checked as arithmetic rather than trusted as a
result. An output reusing an input address carries an input's script type, so the type rule can only
choose that same output or abstain — the two labels are one label, and a document that read their
agreement as corroboration would be counting one fact twice.
"""

import json
from pathlib import Path

import pytest

from decluster.change_special import label_address_reuse, label_type_match
from decluster.experiments import special_change_labels as scl

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "results" / "artifacts" / "special-change-labels-v1.json"
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"


@pytest.fixture(scope="module")
def artifact():
    if not ARTIFACT.is_file():
        pytest.skip("the canonical special-change artifact is not committed")
    return json.loads(ARTIFACT.read_text())


def _pair(artifact, a, b):
    return next(row for row in artifact["agreement"] if {row["a"], row["b"]} == {a, b})


def _row(artifact, label, predictor):
    return next(row for row in artifact["within_tx"]
                if row["label"] == label and row["predictor"] == predictor)


def test_universal_heuristics_agree_with_a_label_neither_of_them_reads(artifact):
    """The non-circular cross-check: values-only label, address- and roundness-only predictors."""
    for predictor in ("round_number", "address_reuse"):
        row = _row(artifact, "optimal_change", predictor)
        assert row["precision"] > 0.75 and row["coverage"] > 0.3


def test_address_reuse_and_type_match_are_one_label(artifact):
    row = _pair(artifact, "address_reuse", "type_match")
    assert row["disagree"] == 0 and row["both"] > 100
    assert "arithmetic rather than evidence" in scl.render_markdown(artifact)


def test_the_type_rule_cannot_contradict_a_reused_address():
    """Why that column is zero, decided on transactions rather than read off the run."""
    reused = {"scriptpubkey_address": "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
    payment = {"scriptpubkey_address": "bc1qaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
    tx = {"txid": "t", "vin": [{"prevout": reused}, {"prevout": reused}],
          "vout": [dict(reused), dict(payment)]}
    assert label_address_reuse(tx) == 0
    assert label_type_match(tx) == 0

    # The type rule abstains rather than dissenting when the payment shares the reused type.
    same_type = {"scriptpubkey_address": "1BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"}
    tx = {"txid": "t", "vin": [{"prevout": reused}, {"prevout": reused}],
          "vout": [dict(reused), dict(same_type)]}
    assert label_address_reuse(tx) == 0
    assert label_type_match(tx) is None


def test_the_onward_spend_arm_is_absent_because_the_data_cannot_carry_it(artifact):
    reach = artifact["onward_spend_reach"]["optimal_change"]
    assert reach["both_outputs_spent"] < 0.05 * reach["labels"], (
        "the cache now holds enough spenders to measure the per-axis arm, so it should be measured "
        "rather than declared out of reach")
    rendered = scl.render_markdown(artifact)
    assert "not measured here" in rendered and "state 4" in rendered


@pytest.mark.reproduction
def test_the_committed_artifact_is_what_a_fresh_run_produces(artifact):
    if not SNAPSHOT.is_file():
        pytest.skip("the block-cache snapshot is not committed")
    scl.verify_artifact(artifact, str(SNAPSHOT))

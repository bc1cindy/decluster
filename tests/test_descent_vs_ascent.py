import gzip

import pytest

from decluster.experiments import descent_vs_ascent as experiment
from decluster.partition import Partition

DATASET = "tests/fixtures/slice_a_channels_2016.ndjson.gz"


def test_reproduce_then_verify_snapshot(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"
    argv = ["--dataset", DATASET]
    assert experiment.main(argv + [
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0
    assert experiment.main(argv + [
        "verify", "--artifact", str(artifact), "--markdown", str(markdown),
    ]) == 0


def test_empty_snapshot_is_rejected(tmp_path):
    dataset = tmp_path / "empty.ndjson.gz"
    with gzip.open(dataset, "wt", encoding="utf-8"):
        pass
    with pytest.raises(experiment.VerificationError, match="snapshot is empty"):
        experiment.build_artifact(dataset)


def test_a_plain_cospend_contributes_no_evidence():
    # Two inputs of one type funding one output: nothing here argues either way, and counting the
    # co-spend itself would let the inherited partition vouch for the claim under test.
    transaction = {
        "txid": "t",
        "vin": [
            {"prevout": {"scriptpubkey_address": a, "scriptpubkey_type": "v0_p2wpkh",
                         "value": 5000}}
            for a in ("a", "b")
        ],
        "vout": [{"scriptpubkey_address": "c", "value": 9000}],
    }
    assert experiment.pair_evidence([(transaction, 0)]) == {}


def test_disagreeing_input_types_argue_against_the_pairing():
    transaction = {
        "txid": "t",
        "vin": [
            {"prevout": {"scriptpubkey_address": "a", "scriptpubkey_type": "v0_p2wpkh",
                         "value": 5000}},
            {"prevout": {"scriptpubkey_address": "b", "scriptpubkey_type": "p2pkh",
                         "value": 5000}},
        ],
        "vout": [{"scriptpubkey_address": "c", "value": 9000}],
    }
    assert experiment.pair_evidence([(transaction, 0)])[("a", "b")] < 0


def test_the_ascent_covering_an_unknown_address_is_refused():
    with pytest.raises(experiment.VerificationError, match="addresses the inherited"):
        experiment._shared_ground({"a": 1}, {"a": 1, "b": 1})


def test_an_address_the_ascent_never_merged_becomes_a_singleton():
    partition = experiment._shared_ground({"a": 1, "b": 1, "c": 1}, {"a": 9, "b": 9})
    assert partition == Partition([["a", "b"], ["c"]])


def test_the_descent_never_coarsens_the_partition_it_inherits():
    artifact = experiment.build_artifact(DATASET)
    runs = artifact["measurement"]["descent"]
    assert runs and all(run["refines_inherited"] for run in runs)


def test_the_ascent_is_finer_than_the_partition_it_replaces():
    artifact = experiment.build_artifact(DATASET)
    measured = artifact["measurement"]
    assert measured["ascent_refines_inherited"]
    assert measured["ascent_blocks"] >= measured["inherited_blocks"]

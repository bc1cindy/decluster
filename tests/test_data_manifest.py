import json
import hashlib
from pathlib import Path

import pytest

from decluster.data_manifest import ManifestError, load_dataset_manifest, load_run_manifest


DIGEST = "a" * 64
ROOT = Path(__file__).resolve().parent.parent


def dataset_document(**overrides):
    document = {
        "schema_version": 1,
        "id": "fixture-v1",
        "title": "Small deterministic fixture",
        "kind": "git_fixture",
        "schema": "tx-ndjson-v1",
        "format": "ndjson",
        "content": {"bytes": 12, "sha256": DIGEST},
        "locations": {"local_path": "tests/fixtures/example.ndjson", "canonical": None, "mirrors": []},
        "source": {"provider": "decluster", "snapshot_time": None, "recipe": None, "recipe_sha256": None},
        "license": {"data": "MIT", "recipe": None},
        "redistribution": "allowed",
        "sensitivity": "synthetic",
        "normalization": {"code_revision": None, "parameters": {}, "parents": []},
        "determinism": {"ordering": "txid ascending", "rng_algorithm": None, "rng_seed": None},
    }
    document.update(overrides)
    return document


def run_document(**overrides):
    document = {
        "schema_version": 1,
        "id": "demo-run-v1",
        "claim_ids": ["ctp.demo"],
        "code": {"revision": "abc123", "dirty": False},
        "command": {"argv": ["python", "-m", "decluster.demo"]},
        "environment": {"python": "3.13", "lock_digest": None, "platform": "any"},
        "datasets": [{"id": "fixture-v1", "sha256": DIGEST}],
        "parameters": {"cutoff": 2},
        "rng": {"algorithm": "MT19937", "seeds": [7]},
        "outputs": [{"path": "results/demo.json", "bytes": 4, "sha256": "b" * 64}],
        "reproducibility": {"level": "bitwise_reproducible", "availability": "complete"},
        "verification": {
            "mode": "exact",
            "argv": ["python", "-m", "pytest", "tests/test_demo.py"],
            "tests": ["tests/test_demo.py::test_result"],
            "properties": ["output matches canonical artifact"],
            "tolerance": None,
        },
        "limitations": ["synthetic fixture"],
    }
    document.update(overrides)
    return document


def write_json(path, document):
    path.write_text(json.dumps(document))
    return path


def test_dataset_manifest_round_trip(tmp_path):
    manifest = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    assert manifest.id == "fixture-v1"
    assert manifest.content.sha256 == DIGEST
    assert manifest.local_path == "tests/fixtures/example.ndjson"
    assert manifest.parameters == {}
    with pytest.raises(TypeError):
        manifest.parameters["new"] = 1


def test_dataset_manifest_rejects_unknown_fields(tmp_path):
    document = dataset_document(surprise=True)
    with pytest.raises(ManifestError, match="unknown=.*surprise"):
        load_dataset_manifest(write_json(tmp_path / "dataset.json", document))


def test_derived_dataset_requires_parent(tmp_path):
    document = dataset_document(kind="derived")
    with pytest.raises(ManifestError, match="must name at least one parent"):
        load_dataset_manifest(write_json(tmp_path / "dataset.json", document))


def test_rng_seed_requires_named_algorithm(tmp_path):
    document = dataset_document()
    document["determinism"] = {"ordering": "stable", "rng_algorithm": None, "rng_seed": 7}
    with pytest.raises(ManifestError, match="rng_seed requires rng_algorithm"):
        load_dataset_manifest(write_json(tmp_path / "dataset.json", document))


def test_run_manifest_resolves_claim_and_dataset(tmp_path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    run = load_run_manifest(
        write_json(tmp_path / "run.json", run_document()),
        claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
    )
    assert run.claim_ids == ("ctp.demo",)
    assert run.datasets[0].id == dataset.id
    assert run.rng_seeds == (7,)
    assert run.reproducibility_level.value == "bitwise_reproducible"
    assert run.verification.mode.value == "exact"
    assert run.verification.tests == ("tests/test_demo.py::test_result",)


def test_run_manifest_rejects_unknown_claim(tmp_path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    with pytest.raises(ManifestError, match="unknown claim ids"):
        load_run_manifest(
            write_json(tmp_path / "run.json", run_document()),
            claim_ids=set(), datasets={dataset.id: dataset},
        )


def test_run_manifest_rejects_dataset_digest_mismatch(tmp_path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    document = run_document()
    document["datasets"] = [{"id": dataset.id, "sha256": "c" * 64}]
    with pytest.raises(ManifestError, match="does not match dataset manifest"):
        load_run_manifest(
            write_json(tmp_path / "run.json", document),
            claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
        )


def test_run_manifest_requires_output(tmp_path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    with pytest.raises(ManifestError, match="outputs: expected non-empty"):
        load_run_manifest(
            write_json(tmp_path / "run.json", run_document(outputs=[])),
            claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
        )


@pytest.mark.parametrize("path", ["../outside.json", "/tmp/out.json", "."])
def test_run_manifest_rejects_unsafe_output_paths(tmp_path, path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    document = run_document()
    document["outputs"] = [{"path": path, "bytes": 4, "sha256": "b" * 64}]
    with pytest.raises(ManifestError, match="safe relative path"):
        load_run_manifest(
            write_json(tmp_path / "run.json", document),
            claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
        )


def test_run_manifest_rejects_duplicate_output_paths(tmp_path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    document = run_document()
    document["outputs"] = document["outputs"] * 2
    with pytest.raises(ManifestError, match="duplicate"):
        load_run_manifest(
            write_json(tmp_path / "run.json", document),
            claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
        )


def test_run_manifest_reports_non_array_datasets(tmp_path):
    with pytest.raises(ManifestError, match="datasets: expected array"):
        load_run_manifest(
            write_json(tmp_path / "run.json", run_document(datasets={})),
            claim_ids={"ctp.demo"}, datasets={},
        )


def test_run_manifest_requires_an_executable_check(tmp_path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    document = run_document()
    document["verification"] = {
        "mode": "exact", "argv": ["verify"], "tests": [], "properties": [], "tolerance": None,
    }
    with pytest.raises(ManifestError, match="at least one test or property"):
        load_run_manifest(
            write_json(tmp_path / "run.json", document),
            claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
        )


@pytest.mark.parametrize("mode,tolerance", [("exact", "1e-9"), ("tolerance", None)])
def test_run_manifest_rejects_incoherent_tolerance(tmp_path, mode, tolerance):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    document = run_document()
    document["verification"] = {
        **document["verification"], "mode": mode, "tolerance": tolerance,
    }
    document["reproducibility"] = {"level": "verified", "availability": "complete"}
    with pytest.raises(ManifestError, match="tolerance"):
        load_run_manifest(
            write_json(tmp_path / "run.json", document),
            claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
        )


def test_bitwise_run_requires_exact_verification(tmp_path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    document = run_document()
    document["verification"] = {
        **document["verification"], "mode": "tolerance", "tolerance": "absolute <= 1e-9",
    }
    with pytest.raises(ManifestError, match="bitwise reproducibility requires exact"):
        load_run_manifest(
            write_json(tmp_path / "run.json", document),
            claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
        )


def test_all_committed_dataset_manifests_match_their_files():
    manifests = sorted((ROOT / "catalog" / "datasets").glob("*.json"))
    assert len(manifests) == 7
    seen = set()
    for path in manifests:
        manifest = load_dataset_manifest(path)
        assert manifest.id not in seen
        seen.add(manifest.id)
        fixture = ROOT / manifest.local_path
        assert fixture.is_file(), manifest.id
        assert fixture.stat().st_size == manifest.content.bytes, manifest.id
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        assert digest == manifest.content.sha256, manifest.id


def test_unknown_fixture_licensing_is_not_presented_as_redistributable():
    for path in (ROOT / "catalog" / "datasets").glob("*.json"):
        manifest = load_dataset_manifest(path)
        if manifest.data_license == "unknown":
            assert manifest.redistribution.value == "unknown"

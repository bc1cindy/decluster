import json
import hashlib
from pathlib import Path

import pytest

from decluster.data_manifest import ManifestError, load_dataset_manifest, load_run_manifest
from decluster.reference_registry import load_claims, load_sources
from decluster.result_artifacts import OutputStatus, verify_run_outputs


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
        "environment": {"python": "3.13", "lock_digest": None, "platform": "any", "dependencies": []},
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


def test_run_manifest_preserves_dependency_provenance(tmp_path):
    dataset = load_dataset_manifest(write_json(tmp_path / "dataset.json", dataset_document()))
    document = run_document()
    document["environment"]["dependencies"] = [{
        "name": "dss", "version": "0.1.0", "source": "https://example.invalid/dss",
        "revision": "abc123", "lock_sha256": DIGEST, "license": "unknown",
        "redistribution": "unknown", "editable": True,
    }]
    run = load_run_manifest(
        write_json(tmp_path / "run.json", document),
        claim_ids={"ctp.demo"}, datasets={dataset.id: dataset},
    )
    assert run.dependencies[0].name == "dss"
    assert run.dependencies[0].editable is True
    assert run.dependencies[0].redistribution.value == "unknown"


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
    expected_ids = {
        "amount-channel-812695-812831-v1",
        "boltzmann-fee-audit-v1",
        "conservation-round-three-v1",
        "entity-bitmex-2019-v1",
        "entity-satoshidice-2013-v1",
        "fingerprint-blkcache-sample-v1",
        "fs-blkcache-2026-09-04-v1",
        "graph-deanon-2016-v1",
        "lumen-explorer-data-v1",
        "merged-anchor-931d6627-v1",
        "ns-bitcoin-left-2016-v1",
        "partition-cuts-300k-2016-v1",
        "ns-bitcoin-right-2016-v1",
        "reid-signatures-v1",
        "slice-a-channels-2016-v1",
        "subtx-demix-cache-2026-09-04-v1",
    }
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
    assert seen == expected_ids


def test_unknown_fixture_licensing_is_not_presented_as_redistributable():
    for path in (ROOT / "catalog" / "datasets").glob("*.json"):
        manifest = load_dataset_manifest(path)
        if manifest.data_license == "unknown":
            assert manifest.redistribution.value == "unknown"


def test_all_committed_run_manifests_resolve_and_their_outputs_match():
    sources = load_sources(ROOT / "catalog" / "ctp-sources.json")
    claims = load_claims(
        ROOT / "catalog" / "ctp-claims.json", {source.id for source in sources}
    )
    datasets = {
        manifest.id: manifest
        for manifest in (
            load_dataset_manifest(path)
            for path in (ROOT / "catalog" / "datasets").glob("*.json")
        )
    }
    paths = sorted((ROOT / "catalog" / "runs").glob("*.json"))
    assert paths
    for path in paths:
        manifest = load_run_manifest(
            path, claim_ids={claim.id for claim in claims}, datasets=datasets,
        )
        checks = verify_run_outputs(manifest, ROOT)
        assert checks
        assert all(check.status is OutputStatus.VERIFIED for check in checks)


def test_every_canonical_artifact_is_owned_by_a_run_manifest():
    sources = load_sources(ROOT / "catalog" / "ctp-sources.json")
    claims = load_claims(
        ROOT / "catalog" / "ctp-claims.json", {source.id for source in sources}
    )
    datasets = {
        manifest.id: manifest
        for manifest in (
            load_dataset_manifest(path)
            for path in (ROOT / "catalog" / "datasets").glob("*.json")
        )
    }
    declared = set()
    for path in sorted((ROOT / "catalog" / "runs").glob("*.json")):
        manifest = load_run_manifest(
            path, claim_ids={claim.id for claim in claims}, datasets=datasets,
        )
        declared.update(output.path for output in manifest.outputs)
    canonical = {
        str(path.relative_to(ROOT))
        for directory in (ROOT / "results" / "artifacts", ROOT / "results" / "generated")
        for path in directory.iterdir()
        if path.is_file()
    }

    assert canonical == declared, (
        f"canonical outputs without manifests={sorted(canonical - declared)}; "
        f"manifest outputs without canonical files={sorted(declared - canonical)}"
    )


# The five `results/*.json` beside the canonical artifacts are not leftovers: each is the frozen
# report a canonical run is held against, and deleting one silently removes that guard. It was
# nearly deleted as redundant during the audit, on a reference sweep that searched the documents
# and the examples but not the tests.
HISTORICAL_BASELINES = {
    "results/boltzmann-fee-audit.json": "tests/test_boltzmann_fee_experiment.py",
    "results/fs-ablation.json": "tests/test_fs_ablation_experiment.py",
    "results/fs-temporal.json": "tests/test_fs_temporal_experiment.py",
    "results/link-prediction.json": "tests/test_link_prediction_experiment.py",
    "results/ns-bitcoin.json": "tests/test_ns_bitcoin_experiment.py",
}


def test_every_historical_baseline_is_present_and_still_guarded():
    for baseline, guard in HISTORICAL_BASELINES.items():
        assert (ROOT / baseline).is_file(), f"{baseline} is the frozen report {guard} compares against"
        assert baseline.split("/", 1)[1] in (ROOT / guard).read_text(), (
            f"{guard} no longer reads {baseline}; if the guard moved, this list has to move with it"
        )


def test_no_other_result_json_sits_outside_the_canonical_directories():
    loose = {
        str(path.relative_to(ROOT))
        for path in (ROOT / "results").glob("*.json")
    }
    assert loose - set(HISTORICAL_BASELINES) == {"results/scale_output.json"}


def test_every_run_manifest_is_carried_by_a_bundle():
    """A run nothing bundles is a result the reproduction gate never executes.

    `descent-vs-ascent-v1` — the run this repository's central comparison rests on — sat outside
    every bundle for a day, verifying its own outputs and never being reproduced from a pinned
    runtime by anyone.
    """
    runs = {path.stem for path in (ROOT / "catalog" / "runs").glob("*.json")}
    carried = set()
    for index in (ROOT / "releases").glob("*.bundle.json"):
        carried.update(json.loads(index.read_text())["runs"])
    assert runs - carried == set(), f"runs no bundle carries: {sorted(runs - carried)}"
    assert carried - runs == set(), f"bundles naming absent runs: {sorted(carried - runs)}"

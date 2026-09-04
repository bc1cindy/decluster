import json
from pathlib import Path

from decluster import data_cli
from decluster.data_catalog import (
    FetchResult,
    FetchStatus,
    PrepareResult,
    PrepareStatus,
)


ROOT = Path(__file__).resolve().parents[1]


def test_list_is_machine_readable_and_deterministic(capsys):
    assert data_cli.main(["--root", str(ROOT), "--json", "list"]) == 0
    records = json.loads(capsys.readouterr().out)
    expected_ids = sorted(path.stem for path in (ROOT / "catalog" / "datasets").glob("*.json"))
    assert [item["id"] for item in records] == expected_ids
    assert set(records[0]) == {"id", "kind", "bytes", "sha256"}


def test_status_reports_without_turning_missing_data_into_command_failure(tmp_path, capsys):
    catalog = tmp_path / "catalog" / "datasets"
    catalog.mkdir(parents=True)
    source = ROOT / "catalog" / "datasets" / "lumen-explorer-data-v1.json"
    (catalog / source.name).write_bytes(source.read_bytes())
    assert data_cli.main(["--root", str(tmp_path), "status"]) == 0
    assert "lumen-explorer-data-v1\tmissing" in capsys.readouterr().out


def test_verify_returns_failure_for_missing_data(tmp_path, capsys):
    catalog = tmp_path / "catalog" / "datasets"
    catalog.mkdir(parents=True)
    source = ROOT / "catalog" / "datasets" / "lumen-explorer-data-v1.json"
    (catalog / source.name).write_bytes(source.read_bytes())
    assert data_cli.main(["--root", str(tmp_path), "verify"]) == 1
    assert "missing" in capsys.readouterr().out


def test_catalog_error_has_distinct_exit_code(tmp_path, capsys):
    assert data_cli.main(["--root", str(tmp_path), "verify"]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "catalog is empty" in captured.err


def test_fetch_delegates_to_api_and_reports_materialized_path(monkeypatch, capsys):
    destination = ROOT / "artifacts" / "sha256" / "example"

    def fake_fetch(dataset, store):
        assert store == ROOT / "custom-store"
        return FetchResult(dataset, FetchStatus.DOWNLOADED, destination, "https://source.invalid")

    monkeypatch.setattr(data_cli, "fetch_dataset", fake_fetch)
    assert data_cli.main([
        "--root", str(ROOT), "--store", "custom-store", "--json",
        "fetch", "lumen-explorer-data-v1",
    ]) == 0
    record = json.loads(capsys.readouterr().out)[0]
    assert record == {
        "id": "lumen-explorer-data-v1",
        "path": str(destination),
        "source_url": "https://source.invalid",
        "status": "downloaded",
    }


def test_fetch_requires_a_known_dataset_id(capsys):
    assert data_cli.main(["--root", str(ROOT), "fetch"]) == 2
    assert "dataset id is required" in capsys.readouterr().err
    assert data_cli.main(["--root", str(ROOT), "fetch", "unknown"]) == 2
    assert "unknown dataset id" in capsys.readouterr().err


def test_prepare_delegates_to_api_without_duplicating_materialization(monkeypatch, capsys):
    destination = ROOT / "tests" / "fixtures" / "lumen_explorer_data.json"

    def fake_prepare(dataset, root, store, *, replace):
        assert root == ROOT
        assert store == ROOT / "artifacts"
        assert replace is True
        return PrepareResult(dataset, PrepareStatus.ALREADY_PREPARED, destination)

    monkeypatch.setattr(data_cli, "prepare_dataset", fake_prepare)
    assert data_cli.main([
        "--root", str(ROOT), "--replace", "prepare", "lumen-explorer-data-v1",
    ]) == 0
    assert capsys.readouterr().out.strip().endswith(
        f"already_prepared\t{destination}"
    )

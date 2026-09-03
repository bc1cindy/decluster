import json
from pathlib import Path

from decluster import bundle_cli


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "releases" / "exact-oracle-evidence-v1.bundle.json"


def test_verify_committed_bundle(capsys):
    assert bundle_cli.main([
        "--index", str(INDEX), "--store", str(ROOT / "artifacts"),
        "--json", "verify",
    ]) == 0
    records = json.loads(capsys.readouterr().out)
    assert len(records) == 7
    assert {record["status"] for record in records} == {"verified"}


def test_verify_missing_store_returns_operational_failure(tmp_path, capsys):
    assert bundle_cli.main([
        "--index", str(INDEX), "--store", str(tmp_path / "missing"), "verify",
    ]) == 1
    assert "missing" in capsys.readouterr().out


def test_bootstrap_cli_delegates_to_api(monkeypatch, tmp_path, capsys):
    called = {}

    def fake_bootstrap(bundle, store, root, *, replace):
        called.update(store=store, root=root, replace=replace, bundle=bundle.id)
        return ()

    monkeypatch.setattr(bundle_cli, "bootstrap_bundle", fake_bootstrap)
    assert bundle_cli.main([
        "--index", str(INDEX), "--store", str(tmp_path / "store"),
        "--root", str(tmp_path / "checkout"), "--replace", "bootstrap",
    ]) == 0
    assert called == {
        "store": tmp_path / "store",
        "root": tmp_path / "checkout",
        "replace": True,
        "bundle": "exact-oracle-evidence-v1",
    }
    assert not capsys.readouterr().out


def test_readiness_cli_is_machine_readable_and_blocked(capsys):
    assert bundle_cli.main([
        "--index", str(INDEX), "--store", str(ROOT / "artifacts"),
        "--root", str(ROOT), "--json", "readiness",
    ]) == 1
    record = json.loads(capsys.readouterr().out)[0]
    assert record["status"] == "blocked"
    assert {issue["kind"] for issue in record["issues"]} == {
        "canonical_location_missing", "mirror_missing",
    }


def test_reproduce_cli_delegates_to_api(monkeypatch, tmp_path, capsys):
    output = tmp_path / "artifact.json"

    def fake_reproduce(bundle, root, work):
        assert bundle.id == "exact-oracle-evidence-v1"
        assert root == tmp_path / "root"
        assert work == tmp_path / "work"
        return (output,)

    monkeypatch.setattr(bundle_cli, "reproduce_bundle", fake_reproduce)
    assert bundle_cli.main([
        "--index", str(INDEX), "--root", str(tmp_path / "root"),
        "--work", str(tmp_path / "work"), "--json", "reproduce",
    ]) == 0
    assert json.loads(capsys.readouterr().out) == [{
        "name": str(output), "status": "reproduced",
    }]

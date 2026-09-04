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
    assert len(records) == 3
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
    assert "capability_missing" in {issue["kind"] for issue in record["issues"]}

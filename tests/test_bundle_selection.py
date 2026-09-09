import json
from pathlib import Path

from decluster import bundle_selection

ROOT = Path(__file__).resolve().parents[1]
TOTAL = len(list((ROOT / "releases").glob("*.bundle.json")))


def _affected(*paths):
    return bundle_selection.affected(ROOT, paths)


def test_an_experiment_module_selects_only_the_runs_that_import_it():
    assert _affected("decluster/experiments/ancestry_contract.py") == {
        "ancestry-contract-v1": "import"
    }


def test_the_source_archive_alone_selects_nothing():
    """Every bundle pins it, so counting it would select all of them on any code edit."""
    archives = sorted((ROOT / "sources").glob("*.tar"))
    assert archives, "no runtime archive is committed"
    assert _affected(f"sources/{archives[0].name}") == {}


def test_a_pinned_output_selects_its_own_bundle():
    assert _affected("results/artifacts/ancestry-contract-v1.json") == {
        "ancestry-contract-v1": "blob"
    }


def test_a_file_read_at_run_time_selects_everything():
    assert len(_affected("catalog/ctp-sources.json")) == TOTAL


def test_a_file_outside_the_archived_surface_selects_nothing():
    assert _affected("README.md", "results/RESULTS-ancestry.md") == {}


def test_the_closure_follows_intra_package_imports_and_stops_at_the_boundary():
    closure = bundle_selection.module_closure(ROOT, "decluster.experiments.intersection_fixture")
    assert "decluster/ancestry.py" in closure
    assert "examples/intersection_pipeline.py" in closure
    assert not any(name.startswith("tests/") for name in closure)


def test_every_run_names_an_entry_module_that_exists():
    for index in sorted((ROOT / "releases").glob("*.bundle.json")):
        for run in json.loads(index.read_text())["runs"]:
            assert bundle_selection.module_closure(ROOT, bundle_selection._entry_module(ROOT, run))


def test_an_empty_selection_prints_a_token_that_matches_no_test(capsys):
    bundle_selection.main(["--root", str(ROOT), "--path", "README.md", "--pytest"])
    expression = capsys.readouterr().out.strip()
    assert expression == bundle_selection.NOTHING
    assert not any(index.stem.startswith(expression) for index in (ROOT / "releases").glob("*"))

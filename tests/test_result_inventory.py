from pathlib import Path

from decluster.result_inventory import inventory_results, summarize


ROOT = Path(__file__).resolve().parents[1]


def test_every_legacy_result_receives_an_explicit_status():
    entries = inventory_results(ROOT)

    assert entries
    assert len({entry.document for entry in entries}) == len(entries)
    assert sum(summarize(entries).values()) == len(entries)


def test_canonical_counterparts_are_not_treated_as_unregistered_history():
    entries = {entry.document: entry for entry in inventory_results(ROOT)}

    candidate = entries["results/RESULTS-candidate-set-intersection.md"]
    oracle = entries["results/RESULTS-exact-oracle-audit.md"]
    assert candidate.canonical_run == "candidate-set-intersection-v1"
    assert oracle.canonical_run == "exact-oracle-audit-v1"
    assert candidate.status == oracle.status == "superseded_by_canonical_run"


def test_migrated_temporal_result_is_bound_to_its_canonical_run():
    entries = {entry.document: entry for entry in inventory_results(ROOT)}
    temporal = entries["results/RESULTS-fs-temporal.md"]

    assert temporal.status == "superseded_by_canonical_run"
    assert temporal.legacy_manifest == "results/manifests/RESULTS-fs-temporal.json"
    assert temporal.canonical_run == "fs-temporal-v1"


def test_unregistered_markdown_is_not_presented_as_reproducible():
    entries = {entry.document: entry for entry in inventory_results(ROOT)}

    assert entries["results/RESULTS-conservation.md"].status == (
        "historical_result_without_run_manifest"
    )

"""Every file a published document names in backticks either exists or is declared unavailable.

Nothing linked `PAPER.md` or the result documents to the tree, so a path could rot silently: three
line references had already drifted by +148, +148 and +270 lines. This is the cheap half of that
gate — it does not check that a number came from an artifact, only that every path a reader is sent
to is a path a reader has.

A path the repository deliberately does not ship is declared here with the reason, the way
`NOT_YET_MIGRATED` declares the results documents that carry no manifest. The list is checked in
both directions: an entry that starts resolving is removed rather than left to grow stale.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

DOCUMENTS = ["PAPER.md", "README.md"] + sorted(
    str(p.relative_to(ROOT)) for p in (ROOT / "results").glob("*.md")
)

# A backticked path, optionally followed by :line or :line-line.
CITATION = re.compile(
    r"`([A-Za-z0-9_][A-Za-z0-9_./-]*"
    r"\.(?:py|md|json|gz|ndjson|tar|sql|toml|yml|txt|whl|lock))(?::\d+(?:-\d+)?)?`"
)

# Documents name modules and fixtures by basename, so a citation resolves against the directories
# a reader would look in.
ROOTS = (
    "", "decluster/", "decluster/experiments/", "decluster/baselines/", "decluster/failure_modes/",
    "results/", "results/generated/", "results/artifacts/", "catalog/", "tests/",
    "tests/fixtures/", "examples/",
)

UNAVAILABLE = {
    "slice_2026.ndjson": "1.1 GB and never committed; the one input this repository cannot restore",
    "catalog/entities.ndjson": "a curated address list the reader supplies; only the example is shipped",
    "epoch_2016_01_391104-392111.ndjson.gz": "a gitignored epoch export from that collection",
    "epoch_2016_01_392112-393119.ndjson.gz": "a gitignored epoch export from that collection",
    "fingerprints.md": "a private reference corpus held outside this repository",
    "sasamoto.md": "a private copy of cond-mat/0106125, cited by its arXiv identifier in the same line",
    "task-2-report.md": "a private working note that predates this repository",
}


def cited_paths():
    for document in DOCUMENTS:
        for path in sorted(set(CITATION.findall((ROOT / document).read_text()))):
            yield document, path


def resolves(path):
    return any((ROOT / prefix / path).exists() for prefix in ROOTS)


def test_documents_are_actually_being_scanned():
    assert len(DOCUMENTS) > 50
    assert sum(1 for _ in cited_paths()) > 400


@pytest.mark.parametrize("document", DOCUMENTS)
def test_every_cited_path_resolves_or_is_declared_unavailable(document):
    dangling = [
        path
        for doc, path in cited_paths()
        if doc == document and not resolves(path) and path not in UNAVAILABLE
    ]
    assert not dangling, (
        f"{document} sends a reader to paths that are not here: {dangling}. Either ship them, cite "
        f"something that exists, or declare them in UNAVAILABLE with the reason."
    )


def test_the_unavailable_list_carries_no_entry_that_now_resolves():
    stale = sorted(path for path in UNAVAILABLE if resolves(path))
    assert not stale, f"UNAVAILABLE still excuses paths that exist: {stale}"


def test_every_unavailable_entry_is_actually_cited():
    cited = {path for _, path in cited_paths()}
    unused = sorted(set(UNAVAILABLE) - cited)
    assert not unused, f"UNAVAILABLE names paths no document cites: {unused}"


def test_every_unavailable_entry_states_a_reason():
    for path, reason in UNAVAILABLE.items():
        assert len(reason.split()) >= 5, f"{path}: the reason is too thin to audit"

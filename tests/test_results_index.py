"""The index of `results/` is generated, so it cannot drift from the catalogue.

Sixty-six written documents and fifty-seven generated ones sat in one directory with no entry
point, and the distinction that matters — which are reproduced by a run and which are prose over
data the repository does not ship — could only be found by opening each.
"""
import subprocess
import sys
from pathlib import Path

from decluster import results_index

ROOT = Path(__file__).resolve().parents[1]


def test_the_index_matches_the_catalogue():
    assert results_index.main(["--root", str(ROOT), "--check"]) == 0, (
        "run `python -m decluster.results_index` and commit the result"
    )


def test_every_generated_document_is_listed_with_its_run():
    index = (ROOT / "results" / "INDEX.md").read_text()
    for path in (ROOT / "results" / "generated").glob("*.md"):
        assert path.name in index, f"{path.name} is not in the index"


def test_every_written_document_is_listed():
    index = (ROOT / "results" / "INDEX.md").read_text()
    for path in (ROOT / "results").glob("RESULTS-*.md"):
        assert path.name in index, f"{path.name} is not in the index"


def test_a_generated_document_is_never_filed_as_written():
    """The two sections are the point; mixing them would make the index worse than none."""
    index = (ROOT / "results" / "INDEX.md").read_text()
    written = index.split("## Written, with a legacy manifest")[1]
    for path in (ROOT / "results" / "generated").glob("*.md"):
        assert f"({path.name})" not in written, f"{path.name} is listed as written"

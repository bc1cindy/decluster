"""Register rules the corpus sets, checked across the tree rather than at two render sites.

`decluster.md`'s own review text — the ~1,500 lines this repository writes in the register of —
uses "ground truth" **zero** times in 1,500 lines. All 98 occurrences in that file are inside the
third-party papers appended to it, and six of those are in scare quotes, used where the labels come
from a simulator and really are known by construction.

This repository's labels are an address-reuse heuristic. It used to say so by negation — "same-owner
labels, not ground truth" — which spends a clause denying a frame the corpus never raises and leaked
the phrase into `results/artifacts/*.json` and the claim catalogue. Two render-time assertions
already banned it in two documents; this bans it everywhere, so the fix cannot be undone one file at
a time.
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PHRASE = re.compile(r"ground[\s-]truth", re.IGNORECASE)

# The store keeps byte-identical copies of tracked files and the archive is a tar of them; both
# follow whatever the text says.
SKIP = ("artifacts/sha256/", "sources/")

# A file that bans the phrase has to name it.
EXEMPT = {
    "tests/test_register.py",
    "tests/test_link_prediction.py",
    "tests/test_oracle_audit.py",
}

SUFFIXES = {".py", ".md", ".json", ".toml", ".yml"}


def tracked_text():
    """Only what git tracks: the ban is about what gets published, not what sits in the checkout."""
    listing = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.splitlines()
    for relative in listing:
        if relative in EXEMPT or any(relative.startswith(part) for part in SKIP):
            continue
        if Path(relative).suffix not in SUFFIXES:
            continue
        path = ROOT / relative
        if path.is_file():
            yield relative, path


def test_the_phrase_the_corpus_never_uses_appears_nowhere():
    offenders = []
    for relative, path in tracked_text():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if PHRASE.search(line):
                offenders.append(f"{relative}:{number}: {line.strip()[:90]}")
    assert not offenders, (
        "say what the labels are — same-owner labels, an address-reuse heuristic — rather than "
        "what they are not:\n  " + "\n  ".join(offenders)
    )


def test_the_ban_is_checked_over_the_tree_and_not_a_handful_of_files():
    assert sum(1 for _ in tracked_text()) > 300

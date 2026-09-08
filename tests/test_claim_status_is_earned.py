"""A claim's status has to be earned by the evidence the catalogue names for it.

Every claim carried `partially_supported`, which made the field carry no information: nineteen of
nineteen identical. The schema distinguishes that from `supported_at_evidence_level`, and the
distinction is the useful one — a claim worded existentially and demonstrated on a deterministic
fixture is not partly proven, it is proven at the level it declares, and its limitations say what it
does not reach rather than what is missing from it.

So the two statuses are held to different rules. A supported claim must name code and be exercised
by a run. A partial one must say what is incomplete, in words a reader can check against the code.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# What this looks for is an unfinished mechanism *here*, which is not the same sentence as "the
# paper's dataset is not reproduced" — that one is scope, and a supported claim may carry it. The
# distinction is the whole point of the two statuses, so the pattern names our own gaps only —
# including a measurement that does not test the claim, such as an auxiliary drawn from the target
# it is supposed to be matched against.
INCOMPLETE = re.compile(
    r"not implemented|not computed|(?<!are )incomplete|not exercise|rather than established"
    r"|does not implement|are not reproduced here|is not implemented|not measured against"
    r"|(?:detection|clustering|pruning|revisitation|modes|model) [a-z ]*(?:are|is) not reproduced",
    re.I)


@pytest.fixture(scope="module")
def claims():
    return json.loads((ROOT / "catalog" / "ctp-claims.json").read_text())["claims"]


@pytest.fixture(scope="module")
def runs_by_claim():
    index = {}
    for path in (ROOT / "catalog" / "runs").glob("*.json"):
        for identifier in json.loads(path.read_text()).get("claim_ids", []):
            index.setdefault(identifier, []).append(path.stem)
    return index


def test_a_supported_claim_is_exercised_by_a_canonical_run(claims, runs_by_claim):
    orphaned = [c["id"] for c in claims
                if c["status"] == "supported_at_evidence_level" and not runs_by_claim.get(c["id"])]
    assert not orphaned, f"claimed as supported with no run behind them: {orphaned}"


def test_a_partial_claim_says_what_is_missing(claims):
    """Otherwise `partially_supported` becomes a place to keep a claim nobody has to finish."""
    silent = []
    for claim in claims:
        if claim["status"] != "partially_supported":
            continue
        limitations = claim["limitations"]
        text = " ".join(limitations) if isinstance(limitations, list) else limitations
        if not INCOMPLETE.search(text):
            silent.append(claim["id"])
    assert not silent, (
        "these are held back as partial without naming what is incomplete:\n  " + "\n  ".join(silent))


def test_the_status_field_distinguishes_something(claims):
    """A field with one value everywhere is decoration; this is what made the audit miss it."""
    statuses = {claim["status"] for claim in claims}
    assert len(statuses) > 1, f"every claim carries {statuses}, so the field says nothing"


def test_a_supported_claim_does_not_also_declare_itself_incomplete(claims):
    """Scope limits belong on a supported claim; an unfinished mechanism does not."""
    contradictory = []
    for claim in claims:
        if claim["status"] != "supported_at_evidence_level":
            continue
        limitations = claim["limitations"]
        text = " ".join(limitations) if isinstance(limitations, list) else limitations
        if INCOMPLETE.search(text):
            contradictory.append((claim["id"], INCOMPLETE.search(text).group(0)))
    assert not contradictory, (
        "supported, yet naming something unfinished:\n  "
        + "\n  ".join(f"{i}: {w}" for i, w in contradictory))

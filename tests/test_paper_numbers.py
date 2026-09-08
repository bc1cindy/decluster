"""Every measurement `PAPER.md` states either resolves to a canonical artifact or is declared.

Nothing linked the paper's numbers to the evidence, so a figure could survive the run that produced
it. `test_cited_paths.py` is the cheap half — it checks that every path a reader is sent to exists.
This is the other half: it takes each measurement-shaped token in the paper and looks for it in the
artifacts.

Matching is by value with a tolerance set by the printed precision, not by provenance: a number that
resolves has *some* artifact carrying it, which is weaker than knowing it came from that one. It is
enough to catch the failure this exists for — a published figure whose run no longer produces it —
and it costs no annotation in the prose.

A number the artifacts cannot carry is declared below with the reason, the way `UNAVAILABLE` and
`NOT_YET_MIGRATED` declare theirs. The list is checked in both directions, so an entry that becomes
backed has to leave it.
"""
import json
import re
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# A measurement, not a section number: a thousands-separated count or a decimal with two or more
# places. The paper writes a negative bits value with U+2212.
MEASUREMENT = re.compile(r"(?<![\w.])([-+−]?\d{1,3}(?:,\d{3})+|[-+−]?\d+\.\d{2,})(?![\w])")

DERIVED = {
    "0.0241": "0.9244 minus 0.9003, both backed: the AUC the same-owner label contributes",
    "0.0161": "the spread of the weight-sensitivity AUC column over the full consistency grid",
    "0.9299": "the low end of the decorrelated-family AUC band across axis choices",
}

UNBACKED = {
    "+6.82": "a per-funder agreement weight from a live report run, not a canonical experiment",
    "2.25": "a sharpening bound from a live ancestry run over the uncommitted cache",
    "0.080": "the change-predictor ordering table, measured on a slice that is not committed",
    "0.320": "the change-predictor ordering table, measured on a slice that is not committed",
    "0.386": "the change-predictor ordering table, measured on a slice that is not committed",
    "0.436": "the change-predictor ordering table, measured on a slice that is not committed",
    "0.484": "the change-predictor ordering table, measured on a slice that is not committed",
    "0.566": "the change-predictor ordering table, measured on a slice that is not committed",
    "0.768": "the change-predictor ordering table, measured on a slice that is not committed",
    "0.775": "the change-predictor ordering table, measured on a slice that is not committed",
    "0.779": "the change-predictor ordering table, measured on a slice that is not committed",
    "105,000": "the size of the BigQuery uniform sample the library bits came from; that export is gone",
    "3,500": "the size of the mempool sample the witness bits came from; that sample is not preserved",
    "165,832": "the size of a growing cache behind a historical AUC, not the committed one",
    "739,889": "the 2024-06-01 slice the change labels were drawn from, which is not committed",
}


def _paper_body():
    """The paper without its reference block: a DOI and an arXiv id are identifiers, not values."""
    text = (ROOT / "PAPER.md").read_text()
    body = text.split("<sub>**Fellegi & Sunter**")[0]
    body = re.sub(r"\[(?:doi|arXiv):[^\]]*\]", " ", body)
    return re.sub(r"https?://\S+", " ", body)


def _values(node, found=None):
    found = set() if found is None else found
    if isinstance(node, dict):
        for item in node.values():
            _values(item, found)
    elif isinstance(node, list):
        for item in node:
            _values(item, found)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        found.add(float(node))
    return found


def artifact_values():
    pool = set()
    for path in sorted((ROOT / "results" / "artifacts").glob("*.json")):
        pool |= _values(json.loads(path.read_text()))
    return pool


def cited():
    return sorted(set(MEASUREMENT.findall(_paper_body())))


@cache
def percent_tokens():
    """The tokens the paper prints as a percentage.

    An artifact stores a rate as a fraction, so the paper's `0.081%` is `0.00081` there and the
    literal token never matches. Scaling only the tokens that carry a `%` keeps the tolerance tied
    to the printed precision; scaling every token would let any of them match a value two orders of
    magnitude away, which is the failure this gate exists to catch.
    """
    return {match.group(1) for match in re.finditer(MEASUREMENT.pattern + r"\s*%", _paper_body())}


def resolves(token, pool):
    target = float(token.replace(",", "").replace("−", "-"))
    places = len(token.split(".")[1]) if "." in token else 0
    tolerance = 0.5 * 10 ** (-places) if places else 0.5
    scales = [(target, tolerance)]
    if token in percent_tokens():
        scales.append((target / 100, tolerance / 100))
    return any(abs(value - scaled) < allowed or abs(value + scaled) < allowed
               for scaled, allowed in scales for value in pool)


@pytest.fixture(scope="module")
def pool():
    return artifact_values()


def test_the_paper_is_actually_being_read():
    assert len(cited()) > 100


def test_every_measurement_resolves_or_is_declared(pool):
    declared = set(DERIVED) | set(UNBACKED)
    stray = [token for token in cited() if token not in declared and not resolves(token, pool)]
    assert not stray, (
        "these are stated as measurements and no artifact carries them:\n  "
        + "\n  ".join(stray)
        + "\nProduce the run, declare the derivation, or say why the data is not here."
    )


def test_no_declaration_covers_a_number_that_now_resolves(pool):
    stale = [token for token in UNBACKED if resolves(token, pool)]
    assert not stale, f"UNBACKED still excuses numbers an artifact now carries: {stale}"


def test_every_declaration_is_cited_by_the_paper():
    tokens = set(cited())
    unused = sorted((set(DERIVED) | set(UNBACKED)) - tokens)
    assert not unused, f"declared and not cited: {unused}"


def test_every_declaration_states_a_reason():
    for token, reason in {**DERIVED, **UNBACKED}.items():
        assert len(reason.split()) >= 8, f"{token}: the reason is too thin to audit"


def test_the_backed_share_is_reported_and_does_not_fall(pool):
    """A floor, not a target: the point is that it can only be raised deliberately."""
    tokens = cited()
    backed = sum(1 for token in tokens if resolves(token, pool))
    assert backed >= 126, f"{backed}/{len(tokens)} resolve; this used to be 126"

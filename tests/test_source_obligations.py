"""Every source's `obligation` has to account for whether a claim cites it.

The catalogue already carries the vocabulary — `context` and `no_code_required` are sources that
inform the writing without asserting anything checkable, while `baseline`, `fixture`, `metric` and
`qualification` are sources some claim is supposed to discharge. Nothing checked that the two
agreed, so three clustering baselines sat uncited beside sixteen carrying the same obligation, and
the difference was invisible.

An unclaimed source with a discharging obligation is either a gap or a decision. This forces it to
be written down as one.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# A source of this kind informs the prose; no claim asserts anything on its behalf.
NO_CLAIM_EXPECTED = {"context", "no_code_required"}

# A source whose obligation would normally be discharged by a claim, and is deliberately not.
EXEMPT = {
    "radix": "a constructive decomposition notebook the counting router reads as method, not an "
             "attack oracle or a mapping-count bound; its own note says so and redistribution "
             "awaits a licence",
}


def sources():
    return json.loads((ROOT / "catalog" / "ctp-sources.json").read_text())["sources"]


def cited():
    claims = json.loads((ROOT / "catalog" / "ctp-claims.json").read_text())["claims"]
    return {source for claim in claims for source in claim["sources"]}


def test_every_source_carries_an_obligation():
    for source in sources():
        assert source.get("obligation"), f"{source['id']} declares no obligation"


def test_a_source_whose_obligation_a_claim_discharges_is_cited_by_one():
    uncited = [
        source["id"]
        for source in sources()
        if source["obligation"] not in NO_CLAIM_EXPECTED
        and source["id"] not in EXEMPT
        and source["id"] not in cited()
    ]
    assert not uncited, (
        f"these carry an obligation a claim is meant to discharge and no claim cites them: "
        f"{uncited}. Cite them from the claim that already covers the material, or write the "
        f"exemption down with its reason."
    )


def test_the_exemptions_are_real_and_reasoned():
    known = {source["id"] for source in sources()}
    for identifier, reason in EXEMPT.items():
        assert identifier in known, f"{identifier} is exempted and is not a source"
        assert identifier not in cited(), f"{identifier} is exempted and is cited; drop the exemption"
        assert len(reason.split()) >= 8, f"{identifier}: the reason is too thin to audit"


def test_the_censorship_aside_is_declared_rather_than_missing():
    """The one gist section with no claim, and the catalogue says why rather than staying silent."""
    aside = next(s for s in sources() if s["id"] == "scam-exchanges")
    assert aside["obligation"] == "no_code_required"
    assert aside["id"] not in cited()

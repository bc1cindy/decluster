import json
from pathlib import Path

import pytest

from decluster.reference_registry import RegistryError, load_claims, load_sources


ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "catalog" / "ctp-sources.json"
CLAIMS = ROOT / "catalog" / "ctp-claims.json"
EXPECTED_CTP_SOURCE_IDS = {
    "androulaki", "bip77", "bip78", "bip79", "boltzmann", "cioh-scroll",
    "cioh-wp", "danezis", "diaz", "flow", "forms", "goldfeder",
    "harrigan-fretter", "kappos", "kelen-seres", "maurer", "maxwell",
    "meiklejohn", "minor-nitpick", "moser-narayanan", "multigraph-nitpick",
    "nick", "ns-linkpred", "ns-netflix", "ns-retro", "ns-social", "ns1r",
    "p2ep", "payjoin-entropy", "proximity", "radix", "reid-harrigan",
    "ron-shamir", "sabouri", "scam-exchanges", "scroll-history",
    "scroll-intersection", "serjantov-danezis", "sudoku", "syverson", "troncoso",
    "tx0", "uih-adamisz", "uih-ghesmati",
}
EXPECTED_CTP_CLAIM_IDS = {
    "ctp.amount.denomination_preparation_fingerprint",
    "ctp.amount.deterministic_partition",
    "ctp.amount.subtransaction_ambiguity",
    "ctp.cioh.collaborative_false_merge",
    "ctp.disclosure.perfect_matching",
    "ctp.disclosure.statistical_longitudinal",
    "ctp.entropy.not_sufficient",
    "ctp.fingerprint.statistical_linkage",
    "ctp.forms.observer_knowledge",
    "ctp.graph.pseudonym_representation",
    "ctp.intersection.longitudinal",
    "ctp.payjoin.receiver_change_readoff",
    "ctp.payjoin.unnecessary_input",
    "ctp.provenance.traceability",
    "ctp.robustness.counterfactual_paths",
    "ctp.social_graph.link_prediction",
    "ctp.social_graph.propagation",
    "ctp.social_graph.structural_linkage",
    "ctp.sparse_dataset.feature_uniqueness",
}


def test_ctp_registry_pins_every_footnote_in_the_reviewed_revision():
    sources = load_sources(SOURCES)
    assert {source.id for source in sources} == EXPECTED_CTP_SOURCE_IDS
    raw = json.loads(SOURCES.read_text())
    assert raw["ctp_revision"] == "51c2ed8f2c2fa817ce44fd662e6f4b5e83577042"
    assert sum(source.url is not None for source in sources) == 37


def test_every_claim_resolves_to_registered_sources():
    sources = load_sources(SOURCES)
    claims = load_claims(CLAIMS, {source.id for source in sources})
    assert {claim.id for claim in claims} == EXPECTED_CTP_CLAIM_IDS


def test_context_only_sources_are_not_silently_dropped():
    sources = load_sources(SOURCES)
    obligations = {source.id: source.obligation.value for source in sources}
    assert obligations["scam-exchanges"] == "no_code_required"
    assert obligations["scroll-history"] == "context"
    assert obligations["flow"] == "qualification"


def test_registry_rejects_unknown_fields(tmp_path):
    raw = json.loads(SOURCES.read_text())
    raw["sources"][0]["surprise"] = True
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(RegistryError, match="unknown=.*surprise"):
        load_sources(path)


def test_claim_registry_rejects_dangling_sources(tmp_path):
    raw = json.loads(CLAIMS.read_text())
    raw["claims"][0]["sources"].append("missing-source")
    path = tmp_path / "claims.json"
    path.write_text(json.dumps(raw))
    sources = load_sources(SOURCES)
    with pytest.raises(RegistryError, match="unknown source ids"):
        load_claims(path, {source.id for source in sources})


def test_registry_rejects_duplicate_source_ids(tmp_path):
    raw = json.loads(SOURCES.read_text())
    raw["sources"].append(dict(raw["sources"][0]))
    path = tmp_path / "sources.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(RegistryError, match="duplicate"):
        load_sources(path)


def test_every_claim_names_code_that_exists_and_a_run_that_exercises_it():
    """A claim's `implementation` and its runs are the two ends of its evidence chain.

    The catalogue went twenty-four commits without being touched while forty modules moved, and
    three claims drifted: one named a comparator instead of the scorer every published AUC comes
    from, one declared no implementation while a run already cited it, and one carried a limitation
    the code had settled. Nothing compared the two ends.
    """
    import re

    root = Path(__file__).resolve().parents[1]
    claims = json.loads((root / "catalog" / "ctp-claims.json").read_text())["claims"]
    exercised = {}
    for path in sorted((root / "catalog" / "runs").glob("*.json")):
        for identifier in json.loads(path.read_text())["claim_ids"]:
            exercised.setdefault(identifier, []).append(path.stem)

    dotted = re.compile(r"\bdecluster\.[A-Za-z_][A-Za-z0-9_.]*")
    problems = []
    for claim in claims:
        implementation = claim.get("implementation") or ""
        named = dotted.findall(implementation)
        if not named:
            problems.append(f"{claim['id']}: names no module")
        for reference in named:
            parts = reference.split(".")
            if not any((root / "/".join(parts[:cut])).with_suffix(".py").exists()
                       or (root / "/".join(parts[:cut])).is_dir()
                       for cut in range(len(parts), 1, -1)):
                problems.append(f"{claim['id']}: {reference} does not resolve")
        if not exercised.get(claim["id"]):
            problems.append(f"{claim['id']}: no run declares it")
    assert not problems, "\n  ".join(problems)

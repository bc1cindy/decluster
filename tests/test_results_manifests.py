"""Every manifest in results/manifests/ is checked against its live source.

An absent source SKIPS with a message naming what went unchecked; it never passes silently. So does
a manifest whose invariants nothing recomputed. A published number went stale once with the suite
green, because nothing recorded what it had been measured on.
"""
import glob
import os

import pytest

from decluster import reproducibility as rp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFESTS = sorted(glob.glob(os.path.join(ROOT, "results", "manifests", "*.json")))
MIGRATED_RUN_DOCS = {
    "RESULTS-analyze.md": "catalog/runs/analyze-contract-v1.json",
    "RESULTS-ancestry.md": "catalog/runs/ancestry-contract-v1.json",
    "RESULTS-ancestry-sparsity.md": "catalog/runs/ancestry-sparsity-v1.json",
    "RESULTS-amount-channel-survey.md": "catalog/runs/amount-channel-survey-v1.json",
    "RESULTS-counting-methods.md": "catalog/runs/counting-methods-v1.json",
    "RESULTS-conservation.md": "catalog/runs/conservation-round-three-v1.json",
    "RESULTS-entity-deanon.md": "catalog/runs/entity-deanon-v1.json",
    "RESULTS-fingerprint-validation.md": "catalog/runs/fingerprint-validation-v1.json",
    "RESULTS-fingerprint-regime.md": "catalog/runs/fingerprint-regime-v1.json",
    "RESULTS-exact-oracle-audit.md": "catalog/runs/exact-oracle-audit-v1.json",
    "RESULTS-path-count.md": "catalog/runs/path-count-contract-v1.json",
    "RESULTS-path-counting-analysis.md": "catalog/runs/path-count-contract-v1.json",
    "RESULTS-reid.md": "catalog/runs/reid-v1.json",
    "RESULTS-slice-a-channels.md": "catalog/runs/slice-channels-v1.json",
}


def _doc(path):
    return os.path.basename(path)[:-len(".json")] + ".md"


@pytest.mark.skipif(not MANIFESTS, reason="no manifests recorded yet")
@pytest.mark.parametrize("manifest", MANIFESTS, ids=_doc)
def test_manifest_is_not_stale(manifest):
    status, message = rp.check_manifest(_doc(manifest), root=ROOT)
    if status == "absent":
        pytest.skip(message)
    if status == "identity-only":
        pytest.skip(message)          # loud: names how many invariants went uncompared
    assert status == "ok", message


def test_every_manifest_names_a_document_that_exists():
    for manifest in MANIFESTS:
        doc = os.path.join(ROOT, "results", _doc(manifest))
        assert os.path.exists(doc), f"{manifest} describes {doc}, which is not in the tree"


# The walker above only checks manifest -> doc: a manifest naming a document that vanished. It has
# no doc -> manifest direction, so a results document with no manifest is invisible to it, silently
# — indistinguishable from one that was never meant to carry one. Migration to canonical run
# manifests is incremental, so requiring every document to carry one now would be dishonest about
# where this phase actually left the instrument. Until later phases file real run manifests, every
# `RESULTS-*.md` is either mapped above, backed by a legacy manifest, or listed here explicitly. A
# new results document that lands in none of those sets fails loudly rather than joining the pile
# invisibly.
NOT_YET_MIGRATED = {
    "RESULTS-3v23-engine.md",
    "RESULTS-ancestry-crossview-feasibility.md",
    "RESULTS-anonymity-set-scale.md",
    "RESULTS-anonymity-set.md",
    "RESULTS-attribute-conditioning.md",
    "RESULTS-attribute-drift.md",
    "RESULTS-bayes-vs-fs.md",
    "RESULTS-broadcast.md",
    "RESULTS-catalog-axes.md",
    "RESULTS-change-id.md",
    "RESULTS-cluster-bits.md",
    "RESULTS-cluster-robustness.md",
    "RESULTS-cluster-scale.md",
    "RESULTS-conspicuous-order.md",
    "RESULTS-contraction-2026.md",
    "RESULTS-def1-sparsity.md",
    "RESULTS-e2e.md",
    "RESULTS-em-m.md",
    "RESULTS-entropy.md",
    "RESULTS-era-sweep.md",
    "RESULTS-fingerprint-sparsity.md",
    "RESULTS-gap1.md",
    "RESULTS-graph-deanon.md",
    "RESULTS-graph-shape.md",
    "RESULTS-intersection.md",
    "RESULTS-match-confidence.md",
    "RESULTS-match-controls.md",
    "RESULTS-multiepoch-local-2016.md",
    "RESULTS-ns-propagation.md",
    "RESULTS-partition-cuts.md",
    "RESULTS-partition-posterior.md",
    "RESULTS-partition-schemes.md",
    "RESULTS-persistence-curve.md",
    "RESULTS-provenance.md",
    "RESULTS-refusing-clusterer.md",
    "RESULTS-rejoin.md",
    "RESULTS-slice-gate-2026.md",
    "RESULTS-special-change.md",
    "RESULTS-subtx-demix.md",
    "RESULTS-temporal.md",
    "RESULTS-topology.md",
    "RESULTS-view-match-2026.md",
    "RESULTS-weight-sensitivity.md",
    "RESULTS-witness-era-drift.md",
    "RESULTS-wp1a.md",
    "RESULTS-wp4.md",
}


def test_every_results_doc_has_a_manifest_or_is_explicitly_not_yet_migrated():
    docs = {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "results", "RESULTS-*.md"))}
    backed = {_doc(m) for m in MANIFESTS} | set(MIGRATED_RUN_DOCS)
    unaccounted = docs - backed - NOT_YET_MIGRATED
    assert not unaccounted, (
        f"no manifest and not listed in NOT_YET_MIGRATED: {sorted(unaccounted)}")
    stale = (NOT_YET_MIGRATED - docs) - backed
    assert not stale, f"NOT_YET_MIGRATED names a document that no longer exists: {sorted(stale)}"


def test_migrated_documents_name_their_canonical_run():
    for doc, manifest in MIGRATED_RUN_DOCS.items():
        assert os.path.isfile(os.path.join(ROOT, manifest))
        with open(os.path.join(ROOT, "results", doc)) as source:
            assert manifest in source.read()


def test_policy_documents_state_five_and_the_direction_rule():
    """The rule state 5 carries is about falsifiability, not about which table a claim sits in: the
    failure it was written for was a green test whose fixture was built to display the claim."""
    policy = open(os.path.join(ROOT, "results", "REPRODUCIBILITY.md")).read()
    assert "## 5. Measured, not separable" in policy
    assert "Being asserted is not the same as being tested" in policy
    assert "could have shown the opposite" in policy

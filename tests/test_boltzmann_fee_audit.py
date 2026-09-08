import json
import os

import pytest

from decluster import reproducibility
from examples.boltzmann_fee_audit import DOC, audit, invariants, values

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = "data/amount-channel-812695-812831-v1.json"


def test_values_requires_complete_multi_input_amounts():
    assert values({"vin": [], "vout": []}) is None
    assert values({"vin": [{"prevout": {"value": 2}}, {"prevout": {"value": 3}}],
                   "vout": [{"value": 4}]}) == ((2, 3), (4,))


def test_committed_report_and_manifest_recompute_from_sample():
    """The snapshot is committed, so this is a check a reader runs rather than one that skips."""
    report = audit(os.path.join(ROOT, SOURCE))
    with open(os.path.join(ROOT, "results", "boltzmann-fee-audit.json")) as handle:
        assert report == json.load(handle)
    status, message = reproducibility.check_manifest(DOC, invariants(report), root=ROOT)
    assert status == "ok", message


def test_roundness_is_recorded_but_does_not_select_mappings():
    report = audit(os.path.join(ROOT, SOURCE), cap=20)
    assert all("fee_roundness" in row for row in report["rows"])
    assert all(set(row) >= {"exact_mappings", "fee_tolerant_mappings"}
               for row in report["rows"])

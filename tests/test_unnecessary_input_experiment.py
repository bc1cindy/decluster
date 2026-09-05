"""Canonical fee-aware unnecessary-input reproduction."""

import json

import pytest

from decluster.experiments import unnecessary_input as experiment


def test_artifact_separates_diagnostic_from_latent_interpretation():
    artifact = experiment.build_artifact()
    equivalence = artifact["observational_equivalence"]

    assert artifact["diagnostic"] == {
        "definition": "blockstream_fee_aware",
        "semantic_version": 2,
        "paper_domain": {
            "minimum_inputs": 2,
            "exact_outputs": 2,
            "amounts": "positive unsigned 64-bit integers",
        },
    }
    assert equivalence["classification"] == "uih2"
    assert equivalence["decision"] == "inconclusive"
    assert equivalence["ownership_inferred"] is False
    assert equivalence["payjoin_identified"] is False
    assert equivalence["payment_output_identified"] is False
    assert equivalence["composition"] is None


def test_artifact_covers_definition_boundaries_and_scope_controls():
    artifact = experiment.build_artifact()

    assert artifact["boundary_cases"]["jointly_funded_uih2"]["status"] == "uih2"
    assert artifact["boundary_cases"]["jointly_funded_uih2"]["gibson_flags"] == [False, False]
    assert artifact["boundary_cases"]["fee_aware_uih1"]["status"] == "uih1"
    assert artifact["boundary_cases"]["equality_boundary"]["status"] == "uih2"
    assert {case["status"] for case in artifact["scope_controls"].values()} == {
        "out_of_scope"
    }


def test_cycle_control_preserves_net_but_not_gross_obligations():
    cycle = experiment.build_artifact()["cycle_control"]

    assert cycle["simple_nonzero_net_balances"] == cycle["cyclic_nonzero_net_balances"]
    assert cycle["simple_gross_amount"] != cycle["cyclic_gross_amount"]


def test_verifier_recomputes_the_diagnostic():
    changed = json.loads(json.dumps(experiment.build_artifact()))
    changed["observational_equivalence"]["payjoin_identified"] = True

    with pytest.raises(experiment.VerificationError, match="fresh diagnostic"):
        experiment.verify_artifact(changed)


def test_cli_reproduces_and_verifies_json_and_markdown(tmp_path):
    artifact = tmp_path / "artifact.json"
    markdown = tmp_path / "result.md"

    assert experiment.main(
        ["reproduce", "--artifact", str(artifact), "--markdown", str(markdown)]
    ) == 0
    assert experiment.main(
        ["verify", "--artifact", str(artifact), "--markdown", str(markdown)]
    ) == 0

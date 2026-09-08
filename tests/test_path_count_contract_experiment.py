from decluster.experiments import path_count_contract as experiment


def test_contract_distinguishes_route_accumulation_from_robust_connectivity():
    artifact = experiment.build_artifact()
    assert artifact["ancestry_distribution"] == artifact["path_count_distribution"]
    assert artifact["count_oracle_invariance"]["distributions_equal"] is True
    # Pinned rather than derived, so a capability cannot start or stop being claimed without
    # someone saying so here. `path_count` still accumulates route mass and is still not the
    # connectivity object; what changed is that `disjoint_routes` now measures that object beside it.
    assert artifact["implemented_capabilities"] == {
        "provenance_route_accumulation": True,
        "edge_disjoint_path_enumeration": True,
        "plausible_flow_capacity": True,
        "k_routes": True,
    }


def test_artifact_round_trip(tmp_path):
    artifact = tmp_path / "result.json"
    markdown = tmp_path / "result.md"
    assert experiment.main([
        "reproduce", "--artifact", str(artifact), "--markdown", str(markdown)
    ]) == 0
    assert experiment.main([
        "verify", "--artifact", str(artifact), "--markdown", str(markdown)
    ]) == 0

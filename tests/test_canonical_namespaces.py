"""Canonical names expose the existing objects without changing numerical behavior."""


def test_rarity_weight_baseline_is_the_existing_implementation():
    from decluster import combiner, rarity_weight_baseline
    assert rarity_weight_baseline.Combiner is combiner.Combiner
    assert rarity_weight_baseline.rarity_score is combiner.rarity_score


def test_single_view_propagation_is_the_existing_implementation():
    from decluster import propagate, single_view_propagation
    assert single_view_propagation.NSPropagator is propagate.NSPropagator
    assert single_view_propagation.propagate_merge is propagate.propagate_merge


def test_ns_social_attack_is_the_reference_baseline():
    from decluster.baselines import narayanan_shmatikov, ns_social_attack
    assert ns_social_attack.propagate is narayanan_shmatikov.propagate


def test_the_two_ancestry_namespaces_select_different_models():
    from decluster import kelen_seres_value_flow, subset_sum_weighted_ancestry
    assert kelen_seres_value_flow.value_flow_link_oracle is not \
        subset_sum_weighted_ancestry.dss_link_oracle


def test_provenance_route_accumulation_is_the_canonical_name():
    from decluster import path_count, weighted_path_count
    from decluster.provenance_route_accumulation import provenance_route_accumulation
    assert provenance_route_accumulation is path_count.provenance_route_accumulation
    assert weighted_path_count.path_count_anonymity is path_count.path_count_anonymity
    assert path_count.path_count_anonymity is path_count.provenance_route_accumulation

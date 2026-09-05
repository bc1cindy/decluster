"""Paper-faithful and differential tests for unnecessary-input analysis."""

from itertools import combinations, permutations

from decluster.baselines.unnecessary_input import (
    UIHStatus,
    analyze_blockstream,
    analyze_transaction,
    blocksci_uih1,
    gibson_flags,
)


def _proper_subset_can_fund(inputs, target):
    """Independent exhaustive oracle used only for small differential tests."""

    return any(
        sum(inputs[index] for index in selected) >= target
        for size in range(1, len(inputs))
        for selected in combinations(range(len(inputs)), size)
    )


def test_multiple_retained_inputs_can_trigger_fee_aware_uih2():
    result = analyze_blockstream([6, 6, 6], [10, 7])
    assert result.status is UIHStatus.UIH2
    assert result.fee == 1
    assert gibson_flags([6, 6, 6], [10, 7]) == (False, False)


def test_fee_and_equality_put_boundary_case_in_uih1():
    result = analyze_blockstream([10, 2], [10, 1])
    assert result.status is UIHStatus.UIH1
    assert result.fee == 1
    assert gibson_flags([10, 2], [10, 1]) == (True, False)


def test_equality_of_smallest_input_and_output_is_uih2():
    result = analyze_blockstream([10, 2], [9, 2])
    assert result.status is UIHStatus.UIH2
    assert blocksci_uih1([10, 2], [9, 2]) is False


def test_tied_minimum_input_has_a_deterministic_witness():
    result = analyze_blockstream([3, 3, 8], [8, 5])
    assert result.status is UIHStatus.UIH2
    assert result.removed_input_index == 0


def test_equal_outputs_do_not_create_change_attribution():
    result = analyze_blockstream([7, 7], [6, 6])
    assert result.status is UIHStatus.UIH1
    assert result.change_output_index is None
    assert result.reason == "equal outputs prevent change attribution"


def test_scope_and_invalid_amounts_are_explicit():
    assert analyze_blockstream([10], [5, 4]).status is UIHStatus.OUT_OF_SCOPE
    assert analyze_blockstream([10, 2], [4, 3, 2]).status is UIHStatus.OUT_OF_SCOPE
    assert analyze_blockstream([10, 0], [5, 4]).status is UIHStatus.INVALID
    assert analyze_blockstream([10, 2], [20, 1]).status is UIHStatus.INVALID


def test_classification_is_invariant_under_input_and_output_permutations():
    expected = UIHStatus.UIH2
    for inputs in permutations([8, 3, 3]):
        for outputs in permutations([7, 6]):
            assert analyze_blockstream(inputs, outputs).status is expected


def test_closed_form_agrees_with_independent_subset_enumeration():
    cases = [
        ([2, 3], [4, 1]),
        ([6, 6, 6], [10, 7]),
        ([10, 2], [10, 1]),
        ([2, 4, 9], [8, 6]),
        ([3, 3, 8], [8, 5]),
    ]
    for inputs, outputs in cases:
        fee = sum(inputs) - sum(outputs)
        expected = _proper_subset_can_fund(inputs, max(outputs) + fee)
        actual = analyze_blockstream(inputs, outputs).status is UIHStatus.UIH2
        assert actual is expected


def test_transaction_adapter_does_not_fall_back_when_amounts_are_missing():
    transaction = {
        "vin": [{"prevout": {"value": 6}}, {"value": 6}, {"prevout": {"value": 6}}],
        "vout": [{"value": 10}, {"value": 7}],
    }
    assert analyze_transaction(transaction).status is UIHStatus.UIH2
    transaction["vin"][0]["prevout"].pop("value")
    assert analyze_transaction(transaction).status is UIHStatus.INVALID


def test_legacy_extractor_and_paper_baseline_are_named_separately():
    from decluster.extractors import x_uih, x_uih_fee_aware

    transaction = {
        "vin": [{"value": 6}, {"value": 6}, {"value": 6}],
        "vout": [{"value": 10}, {"value": 7}],
    }
    assert x_uih(transaction) == "none"
    assert x_uih_fee_aware(transaction) == "uih2"

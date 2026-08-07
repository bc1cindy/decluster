from decluster.conservation import (
    forced_prefixes,
    forced_satoshi,
    min_coins_for,
    forced_count,
    forced_in_round,
    forced_value,
    others_input,
    slack_to_force_one_more,
)


def _tx(inputs, outputs):
    return {
        "vin": [{"prevout": {"value": v}} for v in inputs],
        "vout": [{"value": v} for v in outputs],
    }


def test_others_input_is_the_round_less_the_known_participant():
    assert others_input(100, 40) == 60
    assert others_input(100, 100) == 0
    assert others_input(40, 100) == 0, "a known input larger than the round clamps"


def test_nothing_is_forced_when_the_others_could_have_funded_it_all():
    # others hold 60, three outputs of 20 cost exactly 60
    assert forced_count(100, 40, 20, 3) == 0


def test_the_excess_beyond_what_others_can_fund_is_forced():
    # others hold 50, so they afford two of the three 20s; the third has no source
    assert forced_count(90, 40, 20, 3) == 1


def test_every_output_is_forced_when_the_others_brought_nothing():
    assert forced_count(100, 100, 20, 3) == 3


def test_degenerate_inputs_force_nothing():
    assert forced_count(100, 40, 0, 3) == 0
    assert forced_count(100, 40, 20, 0) == 0
    assert forced_count(100, 40, -5, 3) == 0


def test_forced_in_round_reports_value_forced_and_present():
    # others hold 50: they afford two 20s, so one of three is forced
    tx = _tx([40, 30, 20], [20, 20, 20, 5])
    assert forced_in_round(tx, 40) == [(20, 1, 3)]


def test_forced_in_round_is_empty_when_the_inequality_does_not_bite():
    tx = _tx([10, 45, 45], [20, 20, 20])
    assert forced_in_round(tx, 10) == []


def test_min_count_filters_weak_forcings():
    tx = _tx([40, 30, 20], [20, 20, 20, 5])
    assert forced_in_round(tx, 40, min_count=2) == []


def test_forced_value_totals_the_satoshi_that_must_be_the_participants():
    tx = _tx([40, 30, 20], [20, 20, 20, 5])
    assert forced_value(tx, 40) == 20


def test_the_margin_says_how_far_the_conclusion_is_from_a_boundary():
    # others hold 50 and afford two 20s; 10 more would have bought a third
    assert slack_to_force_one_more(90, 40, 20, 3) == 10
    assert slack_to_force_one_more(100, 40, 20, 3) is None, "nothing forced, no margin"


def test_ignoring_output_fees_keeps_the_bound_a_floor():
    """Fees only raise what the others must have paid, so the count cannot shrink."""
    # Exactly affordable ignoring fees: nothing forced.
    assert forced_count(100, 40, 20, 3) == 0
    # Charging the others even a little makes an output unaffordable.
    with_fee = 21
    assert forced_count(100, 40, with_fee, 3) == 1


def test_forced_satoshi_is_the_excess_over_what_others_brought():
    assert forced_satoshi(100, 40, [20, 20, 20]) == 0, "others hold 60, the set costs 60"
    assert forced_satoshi(90, 40, [20, 20, 20]) == 10
    assert forced_satoshi(100, 100, [20]) == 20, "others brought nothing"


def test_min_coins_takes_the_largest_first():
    assert min_coins_for(0, [10, 10]) == 0
    assert min_coins_for(10, [10, 5, 5]) == 1
    assert min_coins_for(15, [10, 5, 5]) == 2
    assert min_coins_for(25, [10, 5, 5]) == 3, "the whole set barely covers it"


def test_min_coins_returns_the_whole_set_when_it_cannot_cover():
    assert min_coins_for(100, [10, 5]) == 2


def test_pooling_larger_sets_forces_more_satoshi_and_fewer_named_coins():
    # others hold 30. Alone the 20s force 10; pooled with the 10s they force 20.
    tx = _tx([40, 30], [20, 20, 10, 10])
    rows = forced_prefixes(tx, 40)
    assert rows[0][0] == [20] and rows[0][1] == 10
    assert rows[1][0] == [20, 10] and rows[1][1] == 30
    assert rows[1][3] > rows[0][3], "the pool grew"


def test_forced_prefixes_skips_sets_the_others_could_have_funded():
    tx = _tx([10, 90], [20, 20])
    assert forced_prefixes(tx, 10) == []

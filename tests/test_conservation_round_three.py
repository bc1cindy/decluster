"""Regression test pinning the conservation result on the real third round.

`RESULTS-conservation.md` reports that the third round of its six-round spine
forces two of its seven 7.74840978 BTC outputs onto the participant whose input is known,
with a 3.60201666 BTC margin. That number is the repository's headline claim, so
it is pinned here rather than left to a network run.

The fixture is the round reduced to what the argument reads: the total the round
consumed, and the multiset of output values. Conservation needs nothing else —
it never looks at an individual input — so carrying 454 prevouts would add bulk
without adding coverage.

    tx 80f11c778a2f486ffc55b4e8665a94971ae9c350ac53969e9efcbf90478cbf90
"""

from decluster.conservation import (
    forced_in_round,
    forced_value,
    others_input,
    slack_to_force_one_more,
)

ROUND_INPUT = 9000971062          # satoshi consumed by all 454 inputs
PARTICIPANT = 4712126860       # the coin re-registered from round 2
DENOMINATION = 774840978       # 7.74840978 BTC

OUTPUTS = {
    774840978: 7,
    387420489: 2,
    100000000: 8,
    50853104: 1,
    50000000: 4,
    43046721: 6,
    40000000: 1,
    33554432: 11,
    28697814: 9,
    20000000: 13,
    16777216: 5,
    14348907: 1,
    14149484: 1,
    10000000: 16,
    5000000: 15,
    3188646: 24,
    2097152: 17,
    1594323: 27,
    1062882: 23,
    531441: 22,
    354294: 14,
    262144: 29,
    200000: 14,
    131072: 15,
    118098: 15,
    100000: 24,
    99267: 1,
    65536: 20,
    59049: 4,
    50000: 21,
    39366: 24,
    32768: 16,
    20000: 18,
    16384: 11,
    15403: 1,
    13122: 30,
    10000: 32,
}


def _round():
    """The round as conservation reads it: one input carrying the total, and
    every output value at its real multiplicity."""
    return {
        "vin": [{"prevout": {"value": ROUND_INPUT}}],
        "vout": [{"value": v} for v, n in OUTPUTS.items() for _ in range(n)],
    }


def test_the_fixture_is_the_round_it_claims_to_be():
    tx = _round()
    assert sum(OUTPUTS.values()) == 502, "the round paid 502 outputs"
    assert OUTPUTS[DENOMINATION] == 7, "seven outputs at the forced denomination"
    assert sum(v["prevout"]["value"] for v in tx["vin"]) == ROUND_INPUT


def test_round_three_forces_two_of_the_seven_equal_outputs():
    """The result RESULTS-conservation.md reports."""
    tx = _round()
    assert forced_in_round(tx, PARTICIPANT) == [(DENOMINATION, 2, 7)]
    assert forced_value(tx, PARTICIPANT) == 1549681956  # 15.49681956 BTC


def test_the_margin_is_far_from_the_boundary():
    """3.60201666 BTC more would have let the others explain a third output, so
    no rounding and no unmodelled fee can overturn the count."""
    assert (
        slack_to_force_one_more(ROUND_INPUT, PARTICIPANT, DENOMINATION, 7) == 360201666
    )


def test_the_others_could_not_have_afforded_three():
    """The argument itself, stated without the module: the other participants
    brought 42.88844202 BTC, and three of these outputs cost more."""
    others = others_input(ROUND_INPUT, PARTICIPANT)
    assert others == 4288844202
    assert others // DENOMINATION == 5, "the others afford five, not seven"

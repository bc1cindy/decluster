import pytest

from decluster.attribute_drift import (
    CYCLE,
    cycle_gain,
    drift,
    normalise,
    pearson,
    total_variation,
)


def test_total_variation_bounds():
    p = {"a": 1.0}
    assert total_variation(p, p) == 0.0
    assert total_variation(p, {"b": 1.0}) == 1.0
    assert abs(total_variation({"a": .5, "b": .5}, {"a": .75, "b": .25}) - 0.25) < 1e-12


def test_total_variation_handles_disjoint_support():
    """An axis value present in one epoch and absent from the other must count as mass
    moved, not be skipped for missing from one side."""
    assert total_variation({"a": .5, "b": .5}, {"a": 1.0}) == 0.5


def test_normalise_and_pearson():
    assert normalise({"a": 1, "b": 3}) == {"a": .25, "b": .75}
    assert normalise({}) == {}
    assert abs(pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-12
    assert abs(pearson([1, 2, 3], [6, 4, 2]) + 1.0) < 1e-12
    assert pearson([1, 1, 1], [1, 2, 3]) == 0.0


def test_pearson_rejects_empty_or_misaligned_inputs():
    with pytest.raises(ValueError):
        pearson([], [])
    with pytest.raises(ValueError):
        pearson([1], [1, 2])


def test_drift_is_zero_on_a_constant_series():
    series = [{"a": .5, "b": .5}] * 20
    assert set(drift(series, (1, 3, 7)).values()) == {0.0}


def test_cycle_gain_detects_a_planted_weekly_cycle():
    """Alternating a distribution on a 7-epoch period: gaps that are multiples of 7 land
    on the same phase (distance 0), every other gap does not."""
    phases = [{"a": 1.0}, {"a": .5, "b": .5}, {"b": 1.0}, {"a": .5, "b": .5},
              {"a": 1.0}, {"a": .5, "b": .5}, {"b": 1.0}]
    series = [phases[i % CYCLE] for i in range(60)]
    assert cycle_gain(series) < 0.5


def test_cycle_gain_is_neutral_without_a_cycle():
    """A constant series has zero drift at every gap, so there is no cycle to find and no
    ratio to take. Must read neutral, not divide by zero."""
    assert cycle_gain([{"a": .5, "b": .5}] * 60) == 1.0

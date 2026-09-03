import math

import pytest

from decluster.fellegi_sunter import (
    ComparisonField,
    FellegiSunterModel,
    FieldParameters,
    comparison_vector,
    comparison_vectors,
    evaluate,
    fit_model,
    fit_model_for_error_rates,
    fit_supervised,
    thresholds_from_error_rates,
)


def test_classical_agreement_and_disagreement_weights():
    p = FieldParameters(m=0.9, u=0.3)
    assert p.agreement_weight == pytest.approx(math.log2(0.9 / 0.3))
    assert p.disagreement_weight == pytest.approx(math.log2(0.1 / 0.7))


def test_comparison_vectors_are_named_and_can_abstain():
    fields = [
        ComparisonField("name", lambda a, b: a["name"] == b["name"]),
        ComparisonField("age", lambda a, b: None if "age" not in a or "age" not in b
                        else a["age"] == b["age"]),
    ]
    pair = ({"name": "Ada"}, {"name": "Ada", "age": 30})
    assert comparison_vector(*pair, fields) == {"name": True, "age": None}
    assert comparison_vectors([pair], fields) == [{"name": True, "age": None}]


def test_supervised_fit_estimates_m_and_u_from_separate_classes():
    vectors = [
        {"a": True}, {"a": True}, {"a": False},       # matches: 2 / 3
        {"a": True}, {"a": False}, {"a": False},      # non-matches: 1 / 3
    ]
    params = fit_supervised(vectors, [1, 1, 1, 0, 0, 0], alpha=1)
    assert params["a"].m == pytest.approx(3 / 5)
    assert params["a"].u == pytest.approx(2 / 5)


def test_abstentions_do_not_enter_denominators():
    vectors = [{"a": True}, {"a": None}, {"a": False}, {"a": None}]
    p = fit_supervised(vectors, [1, 1, 0, 0], alpha=1)["a"]
    assert p.m == pytest.approx(2 / 3)
    assert p.u == pytest.approx(1 / 3)


def test_score_is_sum_of_log_likelihood_ratios():
    model = FellegiSunterModel(
        {"a": FieldParameters(0.9, 0.3), "b": FieldParameters(0.8, 0.4)},
        non_link_below=-1,
        link_at_or_above=1,
    )
    want = math.log2(0.9 / 0.3) + math.log2((1 - 0.8) / (1 - 0.4))
    assert model.score({"a": True, "b": False}) == pytest.approx(want)
    assert model.contributions({"a": None, "b": True}) == {
        "b": pytest.approx(math.log2(0.8 / 0.4))
    }


def test_thresholds_produce_three_class_decision():
    model = FellegiSunterModel(
        {"a": FieldParameters(0.8, 0.2)},
        non_link_below=-1.5,
        link_at_or_above=1.5,
    )
    assert model.classify({"a": True}) == "link"
    assert model.classify({"a": False}) == "non-link"
    assert model.classify({"a": None}) == "review"


def test_classical_thresholds_are_derived_from_error_rates():
    lower, upper = thresholds_from_error_rates(0.05, 0.10)
    assert lower == pytest.approx(math.log2(0.10 / 0.95))
    assert upper == pytest.approx(math.log2(0.90 / 0.05))

    vectors = ([{"a": True}] * 9 + [{"a": False}] +
               [{"a": True}] + [{"a": False}] * 9)
    model = fit_model_for_error_rates(
        vectors,
        [1] * 10 + [0] * 10,
        false_match_rate=0.05,
        false_non_match_rate=0.10,
    )
    assert model.non_link_below == pytest.approx(lower)
    assert model.link_at_or_above == pytest.approx(upper)


def test_error_rates_must_define_a_review_region():
    with pytest.raises(ValueError, match="review region"):
        thresholds_from_error_rates(0.9, 0.9)


def test_out_of_sample_evaluation_does_not_refit():
    train = [{"a": True}] * 9 + [{"a": False}] + [{"a": True}] + [{"a": False}] * 9
    labels = [1] * 10 + [0] * 10
    model = fit_model(train, labels, non_link_below=-1, link_at_or_above=1, alpha=0.5)
    fitted = model.parameters["a"]

    held_out = [{"a": True}, {"a": False}, {"a": None}]
    result = evaluate(model, held_out, [1, 0, 1])
    assert model.parameters["a"] == fitted
    assert result["decisions"] == ["link", "non-link", "review"]
    assert result["coverage"] == pytest.approx(2 / 3)
    assert result["selective_accuracy"] == 1.0


def test_fit_rejects_a_field_without_both_label_classes():
    with pytest.raises(ValueError, match="active match and non-match"):
        fit_supervised([{"a": True}, {"a": None}], [1, 0])


def test_unknown_field_is_not_silently_ignored():
    model = FellegiSunterModel(
        {"a": FieldParameters(0.8, 0.2)}, -1, 1
    )
    with pytest.raises(ValueError, match="unknown comparison fields"):
        model.score({"a": True, "typo": False})


def test_legacy_fs_name_warns_and_preserves_result():
    from decluster.combiner import fs_score, rarity_score

    axes = [("a", lambda tx: tx["a"], {1: 0.5}, 0.5, lambda _a, _b: False)]
    args = (axes, {"a": 1}, {"a": 1}, 0.9, 10)
    with pytest.warns(DeprecationWarning, match="rarity baseline"):
        legacy = fs_score(*args)
    assert legacy == rarity_score(*args)

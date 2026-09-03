"""Supervised Fellegi--Sunter record linkage.

This module implements the classical binary-comparison model.  It is deliberately
separate from :mod:`decluster.combiner`: that module's value-rarity agreement
score is a useful legacy baseline, but is not a fitted Fellegi--Sunter model.
"""

from dataclasses import dataclass
import math
from typing import Callable, Iterable, Mapping, Optional, Sequence


ComparisonVector = Mapping[str, Optional[bool]]


@dataclass(frozen=True)
class ComparisonField:
    """A named binary comparison; ``None`` means that the field abstains."""

    name: str
    compare: Callable[[object, object], Optional[bool]]


@dataclass(frozen=True)
class FieldParameters:
    """Agreement probabilities conditional on match (m) and non-match (u)."""

    m: float
    u: float

    def __post_init__(self):
        if not 0.0 < self.m < 1.0 or not 0.0 < self.u < 1.0:
            raise ValueError("m and u must be strictly between zero and one")

    @property
    def agreement_weight(self):
        return math.log2(self.m / self.u)

    @property
    def disagreement_weight(self):
        return math.log2((1.0 - self.m) / (1.0 - self.u))


def comparison_vector(left, right, fields: Sequence[ComparisonField]):
    """Build the named agree/disagree/abstain vector for a record pair."""

    out = {}
    for field in fields:
        if field.name in out:
            raise ValueError(f"duplicate comparison field: {field.name}")
        value = field.compare(left, right)
        if value is not None and not isinstance(value, bool):
            raise TypeError(f"comparison {field.name!r} must return bool or None")
        out[field.name] = value
    return out


def comparison_vectors(pairs: Iterable[tuple], fields: Sequence[ComparisonField]):
    """Build comparison vectors for an iterable of ``(left, right)`` pairs."""

    return [comparison_vector(left, right, fields) for left, right in pairs]


def fit_supervised(vectors: Sequence[ComparisonVector], labels: Sequence[bool], *,
                   alpha=0.5):
    """Estimate per-field m and u from labelled training pairs.

    ``True`` labels are known matches and ``False`` labels known non-matches.
    A symmetric Beta(``alpha``, ``alpha``) pseudo-count keeps maximum-likelihood
    estimates finite for fields with all agreements or all disagreements.  An
    abstention is excluded from that field's denominator.
    """

    if len(vectors) != len(labels):
        raise ValueError("vectors and labels must have the same length")
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    names = set()
    for vector in vectors:
        names.update(vector)
    if not names:
        raise ValueError("at least one comparison field is required")

    params = {}
    for name in sorted(names):
        match_agree = match_total = nonmatch_agree = nonmatch_total = 0
        for vector, label in zip(vectors, labels):
            value = vector.get(name)
            if value is None:
                continue
            if label:
                match_total += 1
                match_agree += bool(value)
            else:
                nonmatch_total += 1
                nonmatch_agree += bool(value)
        if not match_total or not nonmatch_total:
            raise ValueError(f"field {name!r} needs active match and non-match observations")
        m = (match_agree + alpha) / (match_total + 2.0 * alpha)
        u = (nonmatch_agree + alpha) / (nonmatch_total + 2.0 * alpha)
        params[name] = FieldParameters(m=m, u=u)
    return params


@dataclass(frozen=True)
class FellegiSunterModel:
    """Fitted parameters plus the classical non-link/review/link thresholds."""

    parameters: Mapping[str, FieldParameters]
    non_link_below: float
    link_at_or_above: float

    def __post_init__(self):
        if not self.parameters:
            raise ValueError("parameters cannot be empty")
        if self.non_link_below >= self.link_at_or_above:
            raise ValueError("non-link threshold must be below link threshold")

    def contributions(self, vector: ComparisonVector):
        """Return each active field's exact log2 likelihood-ratio term."""

        unknown = set(vector) - set(self.parameters)
        if unknown:
            raise ValueError(f"unknown comparison fields: {sorted(unknown)}")
        return {
            name: (parameter.agreement_weight if vector.get(name) else
                   parameter.disagreement_weight)
            for name, parameter in self.parameters.items()
            if vector.get(name) is not None
        }

    def score(self, vector: ComparisonVector):
        """Return the sum of field log2 likelihood ratios."""

        return sum(self.contributions(vector).values())

    def classify(self, vector: ComparisonVector):
        """Classify as ``link``, ``non-link``, or ``review``."""

        score = self.score(vector)
        if score >= self.link_at_or_above:
            return "link"
        if score <= self.non_link_below:
            return "non-link"
        return "review"


def thresholds_from_error_rates(false_match_rate: float,
                                false_non_match_rate: float):
    """Return the classical Fellegi--Sunter decision bounds in log2 units.

    ``false_match_rate`` is the tolerated probability of linking a non-match
    and ``false_non_match_rate`` the tolerated probability of rejecting a
    match.  The likelihood-ratio bounds are converted to the same log2 scale
    used by :class:`FieldParameters`.
    """
    if not 0.0 < false_match_rate < 1.0:
        raise ValueError("false_match_rate must be strictly between zero and one")
    if not 0.0 < false_non_match_rate < 1.0:
        raise ValueError(
            "false_non_match_rate must be strictly between zero and one"
        )
    non_link_below = math.log2(
        false_non_match_rate / (1.0 - false_match_rate)
    )
    link_at_or_above = math.log2(
        (1.0 - false_non_match_rate) / false_match_rate
    )
    if non_link_below >= link_at_or_above:
        raise ValueError("error rates do not define a non-empty review region")
    return non_link_below, link_at_or_above


def fit_model(vectors: Sequence[ComparisonVector], labels: Sequence[bool], *,
              non_link_below: float, link_at_or_above: float, alpha=0.5):
    """Fit parameters on training data and attach caller-selected thresholds."""

    return FellegiSunterModel(
        fit_supervised(vectors, labels, alpha=alpha),
        non_link_below=non_link_below,
        link_at_or_above=link_at_or_above,
    )


def fit_model_for_error_rates(
    vectors: Sequence[ComparisonVector],
    labels: Sequence[bool],
    *,
    false_match_rate: float,
    false_non_match_rate: float,
    alpha=0.5,
):
    """Fit a model using the classical bounds implied by error-rate targets."""
    non_link_below, link_at_or_above = thresholds_from_error_rates(
        false_match_rate, false_non_match_rate
    )
    return fit_model(
        vectors,
        labels,
        non_link_below=non_link_below,
        link_at_or_above=link_at_or_above,
        alpha=alpha,
    )


def evaluate(model: FellegiSunterModel, vectors: Sequence[ComparisonVector],
             labels: Sequence[bool]):
    """Evaluate an already-fitted model on a separate labelled set.

    Keeping fitting out of this function makes train/test leakage explicit.  The
    returned selective accuracy excludes review decisions and reports their
    coverage separately.
    """

    if len(vectors) != len(labels):
        raise ValueError("vectors and labels must have the same length")
    decisions = [model.classify(vector) for vector in vectors]
    decided = [i for i, decision in enumerate(decisions) if decision != "review"]
    correct = sum(
        (decisions[i] == "link") == bool(labels[i])
        for i in decided
    )
    n = len(labels)
    return {
        "n": n,
        "link": decisions.count("link"),
        "non_link": decisions.count("non-link"),
        "review": decisions.count("review"),
        "coverage": len(decided) / n if n else 0.0,
        "selective_accuracy": correct / len(decided) if decided else None,
        "scores": [model.score(vector) for vector in vectors],
        "decisions": decisions,
    }

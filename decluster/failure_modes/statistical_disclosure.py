"""Longitudinal statistical disclosure in the threshold-mix model.

Mix senders and recipients are carried as `SubjectKind.CLUSTER`. There is no mix-participant
kind in the vocabulary and none is added for a synthetic fixture; the reuse is notation, and
nothing here reads a Bitcoin wallet cluster out of it.
"""

from dataclasses import dataclass
from math import isfinite

from ..domain import (
    AttackReport,
    CorrespondentDistributionEvidence,
    EvidenceChannel,
    EvidenceContext,
    Inconclusive,
    PersistentCorrespondentRanked,
    Subject,
    SubjectKind,
)


@dataclass(frozen=True)
class StatisticalDisclosureScenario:
    identifier: str
    target: Subject
    correspondents: tuple[Subject, ...]
    background_distribution: tuple[float, ...]
    rounds: tuple[tuple[Subject, ...], ...]

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("scenario identifier must not be empty")
        if len(self.correspondents) < 2 or len(set(self.correspondents)) != len(
            self.correspondents
        ):
            raise ValueError("scenario requires at least two unique correspondents")
        if self.target in self.correspondents:
            raise ValueError("target must not be a correspondent")
        if len(self.background_distribution) != len(self.correspondents):
            raise ValueError("background distribution must cover every correspondent")
        if any(
            not isfinite(probability) or probability < 0.0
            for probability in self.background_distribution
        ):
            raise ValueError("background probabilities must be finite and non-negative")
        if abs(sum(self.background_distribution) - 1.0) > 1e-9:
            raise ValueError("background probabilities must sum to one")
        if not self.rounds:
            raise ValueError("scenario requires observed rounds")
        batch_sizes = {len(round_) for round_ in self.rounds}
        if len(batch_sizes) != 1 or next(iter(batch_sizes)) < 2:
            raise ValueError("rounds must have one batch size of at least two")
        allowed = set(self.correspondents)
        if any(receiver not in allowed for round_ in self.rounds for receiver in round_):
            raise ValueError("round contains an unknown correspondent")

    @property
    def batch_size(self) -> int:
        return len(self.rounds[0])


def _correspondent(identifier: str) -> Subject:
    return Subject(SubjectKind.CLUSTER, identifier)


def paired_examples() -> tuple[StatisticalDisclosureScenario, StatisticalDisclosureScenario]:
    correspondents = tuple(_correspondent(name) for name in ("alice", "bob", "carol", "dave"))
    target = Subject(SubjectKind.CLUSTER, "observed-sender")
    background = (0.25, 0.25, 0.25, 0.25)
    background_messages = (
        (correspondents[0], correspondents[1], correspondents[2]),
        (correspondents[1], correspondents[2], correspondents[3]),
        (correspondents[2], correspondents[3], correspondents[0]),
        (correspondents[3], correspondents[0], correspondents[1]),
    )
    persistent_rounds = tuple(
        (correspondents[0],) + messages for messages in background_messages
    )
    null_rounds = tuple(
        (correspondents[index],) + messages
        for index, messages in enumerate(background_messages)
    )
    return (
        StatisticalDisclosureScenario(
            "persistent-correspondent",
            target,
            correspondents,
            background,
            persistent_rounds,
        ),
        StatisticalDisclosureScenario(
            "background-matched-control",
            target,
            correspondents,
            background,
            null_rounds,
        ),
    )


def estimate(scenario: StatisticalDisclosureScenario) -> CorrespondentDistributionEvidence:
    counts = {correspondent: 0 for correspondent in scenario.correspondents}
    for round_ in scenario.rounds:
        for correspondent in round_:
            counts[correspondent] += 1
    denominator = len(scenario.rounds) * scenario.batch_size
    scores = tuple(
        (
            correspondent,
            scenario.batch_size * counts[correspondent] / denominator
            - (scenario.batch_size - 1) * background,
        )
        for correspondent, background in zip(
            scenario.correspondents, scenario.background_distribution
        )
    )
    context = EvidenceContext(
        adversary="global passive observer who knows the target-active rounds",
        observables=("recipient multiset per round", "batch size", "background distribution"),
        hypothesis="the target has a persistent correspondent distribution distinct from background",
        algorithm="Danezis threshold-mix statistical disclosure estimator, equation 2",
        dataset="deterministic synthetic threshold-mix fixture",
        limitations=(
            "target activity and the background distribution are supplied",
            "the threshold-mix model is not an ownership model for Bitcoin",
        ),
    )
    return CorrespondentDistributionEvidence(
        scenario.target,
        scores,
        len(scenario.rounds),
        scenario.batch_size,
        context,
    )


def evaluate(scenario: StatisticalDisclosureScenario) -> AttackReport:
    evidence = estimate(scenario)
    ranked = sorted(evidence.scores, key=lambda item: item[1], reverse=True)
    margin = ranked[0][1] - ranked[1][1]
    if margin > 1e-12:
        outcomes = (PersistentCorrespondentRanked(evidence, ranked[0][0], margin),)
    else:
        outcomes = (Inconclusive((scenario.target,), "no unique correspondent exceeds background"),)
    return AttackReport(
        identifier=f"ctp.statistical-disclosure.{scenario.identifier}",
        attack="longitudinal statistical disclosure",
        subjects=(scenario.target,) + scenario.correspondents,
        channels=(EvidenceChannel("correspondent_distribution", (evidence,)),),
        outcomes=outcomes,
        limitations=(
            "deterministic synthetic threshold-mix fixture",
            "the model assumes one target message and batch_size minus one background messages per round",
            "the result ranks persistent correspondents and does not attribute Bitcoin ownership",
            "the fixture does not estimate real-world attack frequency or confidence",
            "the estimator is implemented; the paper's applicability and efficiency section is not"
            " — neither the signal-to-noise condition that decides whether the attack is possible"
            " at all, nor the bound on observations needed for a stated confidence. Those are the"
            " part of the source that speaks to a rate, so no claim about how fast certainty is"
            " gained is covered here",
        ),
    )

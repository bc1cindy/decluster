"""Profile-weighted perfect-matching disclosure for one threshold-mix round.

Sent and received messages are carried as `SubjectKind.MAPPING`. There is no message kind in
the vocabulary and none is added for a synthetic fixture; the reuse is notation.

One deliberate divergence from the paper. Its equation 4 linearizes the joint probability by
edge weights `log(P)`, and it defines `log(0) = -inf` expressly so the assignment algorithm
still returns a matching -- the paper notes that the substitution "solely prevents numerical
errors and has no influence on the output M". Here a permutation containing a zero-probability
pair is dropped instead, and a round in which every permutation contains one abstains rather
than returning a matching the profiles say is impossible. That is the repository's refuse-only
posture, not the paper's behaviour, and it changes the output where the paper's does not.
Weights are natural logs; base is immaterial to the argmax but the reported log-likelihood is
not on the paper's base-10 scale.
"""

from dataclasses import dataclass
from itertools import permutations
from math import isclose, isfinite, log
from typing import Optional

from ..domain import (
    AbstentionEvidence,
    AttackReport,
    EvidenceChannel,
    EvidenceContext,
    Inconclusive,
    MessageAssignmentRecovered,
    PerfectMatchingEvidence,
    Subject,
    SubjectKind,
)


@dataclass(frozen=True)
class PerfectMatchingScenario:
    identifier: str
    senders: tuple[Subject, ...]
    receivers: tuple[Subject, ...]
    profile_weights: tuple[tuple[float, ...], ...]

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("scenario identifier must not be empty")
        size = len(self.senders)
        if size < 2 or len(self.receivers) != size:
            raise ValueError("scenario requires equal sides of size at least two")
        if len(set(self.senders)) != size or len(set(self.receivers)) != size:
            raise ValueError("message nodes on each side must be unique")
        if len(self.profile_weights) != size or any(
            len(row) != size for row in self.profile_weights
        ):
            raise ValueError("profile matrix must be square and match the round")
        if any(
            not isfinite(weight) or not 0.0 <= weight <= 1.0
            for row in self.profile_weights
            for weight in row
        ):
            raise ValueError("profile weights must be finite probabilities")
        if size > 8:
            raise ValueError("diagnostic enumerator is limited to eight messages")


@dataclass(frozen=True)
class PerfectMatchingAnalysis:
    assignments: tuple[tuple[tuple[Subject, Subject], ...], ...]
    log_likelihood: Optional[float]


def _message(side: str, position: int) -> Subject:
    return Subject(SubjectKind.MAPPING, (side, position))


def paired_examples() -> tuple[PerfectMatchingScenario, PerfectMatchingScenario]:
    senders = tuple(_message("sender-message", position) for position in range(3))
    receivers = tuple(_message("receiver-message", position) for position in range(3))
    return (
        PerfectMatchingScenario(
            "joint-assignment",
            senders,
            receivers,
            (
                (0.60, 0.35, 0.05),
                (0.55, 0.40, 0.05),
                (0.05, 0.15, 0.80),
            ),
        ),
        PerfectMatchingScenario(
            "uniform-profile-control",
            senders,
            receivers,
            (
                (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
                (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
                (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
            ),
        ),
    )


def analyze(scenario: PerfectMatchingScenario) -> PerfectMatchingAnalysis:
    best = None
    assignments: list[tuple[tuple[Subject, Subject], ...]] = []
    for receiver_order in permutations(range(len(scenario.receivers))):
        weights = tuple(
            scenario.profile_weights[sender_index][receiver_index]
            for sender_index, receiver_index in enumerate(receiver_order)
        )
        if any(weight == 0.0 for weight in weights):
            continue
        likelihood = sum(log(weight) for weight in weights)
        assignment = tuple(
            (scenario.senders[sender_index], scenario.receivers[receiver_index])
            for sender_index, receiver_index in enumerate(receiver_order)
        )
        if best is None or (
            likelihood > best and not isclose(likelihood, best, abs_tol=1e-12)
        ):
            best = likelihood
            assignments = [assignment]
        elif isclose(likelihood, best, abs_tol=1e-12):
            assignments.append(assignment)
    return PerfectMatchingAnalysis(tuple(assignments), best)


def evaluate(scenario: PerfectMatchingScenario) -> AttackReport:
    analysis = analyze(scenario)
    context = EvidenceContext(
        adversary="global passive observer with estimated sender profiles",
        observables=("sender-message multiset", "receiver-message multiset", "sender profiles"),
        hypothesis="one bijective assignment jointly maximizes the round likelihood",
        algorithm="exact diagnostic enumeration of the PMDA maximum-weight perfect-matching objective",
        dataset="deterministic synthetic threshold-mix round",
        limitations=(
            "sender profiles are supplied rather than estimated from a longitudinal trace",
            "enumeration is a small-fixture oracle, not the scalable assignment algorithm",
            "zero-probability pairs abstain here; under the paper's log(0) = -inf convention the"
            " assignment algorithm still returns a matching",
        ),
    )
    if analysis.log_likelihood is None:
        evidence = AbstentionEvidence(
            scenario.senders + scenario.receivers,
            "no positive-probability perfect matching",
            context,
        )
        outcomes = (Inconclusive(scenario.senders + scenario.receivers, evidence.reason),)
    else:
        evidence = PerfectMatchingEvidence(
            scenario.senders,
            scenario.receivers,
            analysis.assignments,
            analysis.log_likelihood,
            context,
        )
        if len(analysis.assignments) == 1:
            outcomes = (MessageAssignmentRecovered(evidence, analysis.assignments[0]),)
        else:
            outcomes = (
                Inconclusive(
                    scenario.senders + scenario.receivers,
                    "multiple perfect matchings share the maximum likelihood",
                ),
            )
    return AttackReport(
        identifier=f"ctp.perfect-matching-disclosure.{scenario.identifier}",
        attack="profile-weighted perfect-matching disclosure",
        subjects=scenario.senders + scenario.receivers,
        channels=(EvidenceChannel("joint_round_assignment", (evidence,)),),
        outcomes=outcomes,
        limitations=(
            "deterministic synthetic threshold-mix fixture",
            "the profile-estimation phase is supplied and tested separately by statistical disclosure",
            "the result links messages within one round and does not attribute Bitcoin ownership",
            "the cited paper's simulations and success rates are not reproduced",
        ),
    )

"""Receiver-side change read-off in a many-senders/one-receiver payjoin.

The receiver knows its own coins and each sender's negotiated payment, so every
candidate (input, change) pair must satisfy ``input - payment == change``.  Read
sender by sender the constraint is often ambiguous; enumerating the perfect
matchings propagates it across senders and can leave a single reading.
"""

from dataclasses import dataclass
from typing import Iterator, Mapping, Sequence

from ..domain import (
    AbstentionEvidence,
    AttackReport,
    CandidateSetEvidence,
    ConditionalLinksMeasured,
    EvidenceChannel,
    EvidenceContext,
    Inconclusive,
    Subject,
    SubjectKind,
    UnanimousMappingLinksEvidence,
)

MAX_SENDERS = 8

# Exact value-conserving block mappings are not a usable enumeration here: they
# require every block to conserve value, whereas the receiver's block absorbs
# the payments (40 in against 160 out below).  The true sub-transaction
# structure is therefore not a member of that family for any positive payment.


@dataclass(frozen=True)
class ReadOffScenario:
    """One transaction plus the payment amounts the receiver negotiated."""

    identifier: str
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]
    receiver_input: int
    receiver_output: int
    payments: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("scenario identifier must not be empty")
        if any(value <= 0 for value in self.inputs + self.outputs):
            raise ValueError("coin amounts must be positive")
        # A non-zero fee would need a declared allocation rule between the
        # sub-transactions; the read-off does not observe one.
        if sum(self.inputs) != sum(self.outputs):
            raise ValueError("read-off requires a fee-free conservation model")
        if not 0 <= self.receiver_input < len(self.inputs):
            raise ValueError("receiver input index out of range")
        if not 0 <= self.receiver_output < len(self.outputs):
            raise ValueError("receiver output index out of range")
        senders = tuple(name for name, _ in self.payments)
        if not senders or len(set(senders)) != len(senders):
            raise ValueError("sender names must be unique and non-empty")
        if any(not name or amount <= 0 for name, amount in self.payments):
            raise ValueError("each sender must have a name and a positive payment")
        if len(senders) > MAX_SENDERS:
            raise ValueError("read-off enumeration is limited to eight senders")
        # The form gives each sender exactly one input and one change output.
        if len(self.inputs) != len(senders) + 1 or len(self.outputs) != len(senders) + 1:
            raise ValueError("each sender contributes one input and one change output")
        paid = sum(amount for _, amount in self.payments)
        if self.outputs[self.receiver_output] != self.inputs[self.receiver_input] + paid:
            raise ValueError("receiver output must equal its input plus the payments")

    @classmethod
    def from_payments(
        cls,
        identifier: str,
        inputs: Sequence[int],
        outputs: Sequence[int],
        receiver_input: int,
        receiver_output: int,
        payments: Mapping[str, int],
    ) -> "ReadOffScenario":
        return cls(
            identifier,
            tuple(inputs),
            tuple(outputs),
            receiver_input,
            receiver_output,
            tuple(payments.items()),
        )

    @property
    def senders(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.payments)

    @property
    def sender_inputs(self) -> tuple[int, ...]:
        return tuple(i for i in range(len(self.inputs)) if i != self.receiver_input)

    @property
    def change_outputs(self) -> tuple[int, ...]:
        return tuple(i for i in range(len(self.outputs)) if i != self.receiver_output)


@dataclass(frozen=True)
class ChangeReadOff:
    """Per-sender candidate change before and after propagating the constraint."""

    scenario: ReadOffScenario
    local_candidates: tuple[tuple[str, frozenset[int]], ...]
    feasible_candidates: tuple[tuple[str, frozenset[int]], ...]
    matchings: tuple[tuple[tuple[str, int, int], ...], ...]
    readings: tuple[tuple[tuple[str, int, int], ...], ...]

    @property
    def unanimous_links(self) -> tuple[tuple[int, int], ...]:
        if not self.matchings:
            return ()
        shared = set.intersection(
            *({(source, target) for _, source, target in matching} for matching in self.matchings)
        )
        return tuple(sorted(shared))


def ns1r_examples() -> tuple[ReadOffScenario, ReadOffScenario]:
    return (
        ReadOffScenario(
            "consolidating-receiver",
            (40, 50, 60, 90),
            (160, 30, 30, 20),
            0,
            0,
            (("Alice", 20), ("Bob", 30), ("Carol", 70)),
        ),
        ReadOffScenario(
            "evenly-spaced-control",
            (20, 40, 50, 60),
            (80, 30, 20, 40),
            0,
            0,
            (("Alice", 10), ("Bob", 30), ("Carol", 20)),
        ),
    )


def _pairs(scenario: ReadOffScenario, payment: int) -> frozenset[tuple[int, int]]:
    return frozenset(
        (source, target)
        for source in scenario.sender_inputs
        for target in scenario.change_outputs
        if scenario.inputs[source] - payment == scenario.outputs[target]
    )


def _matchings(
    scenario: ReadOffScenario,
    feasible: Sequence[frozenset[tuple[int, int]]],
    position: int = 0,
    used_inputs: frozenset[int] = frozenset(),
    used_outputs: frozenset[int] = frozenset(),
) -> Iterator[tuple[tuple[str, int, int], ...]]:
    if position == len(feasible):
        yield ()
        return
    sender = scenario.senders[position]
    for source, target in sorted(feasible[position]):
        if source in used_inputs or target in used_outputs:
            continue
        for rest in _matchings(
            scenario,
            feasible,
            position + 1,
            used_inputs | {source},
            used_outputs | {target},
        ):
            yield ((sender, source, target),) + rest


def analyze(scenario: ReadOffScenario) -> ChangeReadOff:
    feasible = [_pairs(scenario, payment) for _, payment in scenario.payments]
    matchings = tuple(_matchings(scenario, feasible))
    local = tuple(
        (sender, frozenset(target for _, target in pairs))
        for sender, pairs in zip(scenario.senders, feasible)
    )
    reachable: dict[str, set[int]] = {sender: set() for sender in scenario.senders}
    readings = set()
    for matching in matchings:
        for sender, _, target in matching:
            reachable[sender].add(target)
        readings.add(
            tuple(
                (sender, scenario.inputs[source], scenario.outputs[target])
                for sender, source, target in matching
            )
        )
    return ChangeReadOff(
        scenario,
        local,
        tuple((sender, frozenset(reachable[sender])) for sender in scenario.senders),
        matchings,
        tuple(sorted(readings)),
    )


def _sender(name: str) -> Subject:
    return Subject(SubjectKind.MAPPING, ("sender", name))


def _coin(side: str, index: int) -> Subject:
    return Subject(SubjectKind.COIN, (side, index))


def evaluate(scenario: ReadOffScenario) -> AttackReport:
    analysis = analyze(scenario)
    senders = tuple(_sender(name) for name in scenario.senders)
    sources = tuple(_coin("input", index) for index in scenario.sender_inputs)
    targets = tuple(_coin("output", index) for index in scenario.change_outputs)
    context = EvidenceContext(
        adversary="the receiver of a many-senders/one-receiver payjoin",
        observables=(
            "input and output amounts",
            "the receiver's own input and output",
            "the payment amount negotiated with each sender",
        ),
        hypothesis="each sender's change is the remainder of one input after its payment",
        algorithm="enumeration of the perfect matchings between senders and remainder-consistent input/output pairs",
        dataset="deterministic synthetic NS1R fixture",
        limitations=(
            "the negotiated payments are supplied rather than observed",
            "the form is assumed to give each sender one input and one change output",
            "change outputs of equal amount stay interchangeable as coins",
        ),
    )
    local = EvidenceChannel(
        "per_sender_remainder",
        tuple(
            CandidateSetEvidence(
                _sender(name),
                frozenset(_coin("output", index) for index in candidates),
                context,
            )
            for name, candidates in analysis.local_candidates
        ),
    )
    if not analysis.matchings:
        abstention = AbstentionEvidence(
            senders, "no assignment satisfies every sender's remainder", context
        )
        channels = (local, EvidenceChannel("matching_propagation", (abstention,)))
        outcomes = (Inconclusive(senders, abstention.reason),)
    else:
        propagated = EvidenceChannel(
            "matching_propagation",
            tuple(
                CandidateSetEvidence(
                    _sender(name),
                    frozenset(_coin("output", index) for index in candidates),
                    context,
                )
                for name, candidates in analysis.feasible_candidates
            ),
        )
        links = UnanimousMappingLinksEvidence(
            sources,
            targets,
            len(analysis.matchings),
            tuple(
                (_coin("input", source), _coin("output", target))
                for source, target in analysis.unanimous_links
            ),
            context,
        )
        channels = (local, propagated)
        outcomes = (ConditionalLinksMeasured(links),)
        if len(analysis.readings) > 1:
            outcomes += (
                Inconclusive(
                    senders, "several sender-to-remainder readings survive propagation"
                ),
            )
    return AttackReport(
        identifier=f"ctp.ns1r-change-readoff.{scenario.identifier}",
        attack="receiver-side change read-off under declared payment amounts",
        subjects=senders + sources + targets,
        channels=channels,
        outcomes=outcomes,
        limitations=(
            "the payment amounts are the receiver's declared knowledge, not an on-chain observable",
            "a fee would require a declared allocation rule between sub-transactions",
            "a reading assigns amounts, not coin identity, when change amounts coincide",
            "the result is relative to the declared model and does not attribute ownership",
        ),
    )

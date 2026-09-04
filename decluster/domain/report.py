"""Structured reports that preserve adversarial evidence by channel."""

from dataclasses import dataclass
from math import isfinite
from typing import Optional

from .evidence import Evidence, Subject
from .outcome import Outcome


@dataclass(frozen=True)
class EvidenceChannel:
    """Evidence emitted by one independently identifiable mechanism."""

    identifier: str
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("channel identifier must not be empty")
        if not self.evidence:
            raise ValueError("channel must contain evidence")


@dataclass(frozen=True)
class ExperimentalComposition:
    """Non-normative summary whose inputs remain available in the report."""

    method: str
    channel_ids: tuple[str, ...]
    value: float
    unit: str
    interpretation: str

    def __post_init__(self) -> None:
        if not self.method or not self.unit or not self.interpretation:
            raise ValueError("composition metadata must not be empty")
        if not self.channel_ids or len(set(self.channel_ids)) != len(self.channel_ids):
            raise ValueError("composition requires unique channel identifiers")
        if not isfinite(self.value):
            raise ValueError("composition value must be finite")


@dataclass(frozen=True)
class AttackReport:
    """Evidence and outcomes for one adversarial scenario.

    A report is not a privacy certificate.  Its channels remain separate even
    when an experimental composition is attached.
    """

    identifier: str
    attack: str
    subjects: tuple[Subject, ...]
    channels: tuple[EvidenceChannel, ...]
    outcomes: tuple[Outcome, ...]
    limitations: tuple[str, ...]
    composition: Optional[ExperimentalComposition] = None

    def __post_init__(self) -> None:
        for label, value in (("identifier", self.identifier), ("attack", self.attack)):
            if not value:
                raise ValueError(f"{label} must not be empty")
        if not self.subjects or len(set(self.subjects)) != len(self.subjects):
            raise ValueError("report requires unique subjects")
        channel_ids = tuple(channel.identifier for channel in self.channels)
        if len(set(channel_ids)) != len(channel_ids):
            raise ValueError("report channel identifiers must be unique")
        if not self.outcomes:
            raise ValueError("report requires at least one outcome")
        if any(not limitation for limitation in self.limitations):
            raise ValueError("limitations must contain non-empty values")
        if self.composition is not None:
            unknown = set(self.composition.channel_ids) - set(channel_ids)
            if unknown:
                raise ValueError(f"composition references unknown channels: {sorted(unknown)}")

    def evidence(self) -> tuple[Evidence, ...]:
        """Flatten evidence without discarding its channel organization."""
        return tuple(item for channel in self.channels for item in channel.evidence)

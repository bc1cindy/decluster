"""Executable CTP matrix of collaborative forms and observer knowledge."""

from dataclasses import dataclass
from enum import Enum


class CollaborativeForm(str, Enum):
    ORDINARY_TWO_INPUT = "ordinary_two_input"
    P2EP = "p2ep"
    BIP79 = "bip79_bustapay"
    BIP78 = "bip78_sync_payjoin"
    BIP77 = "bip77_async_payjoin"
    NS1R = "many_senders_one_receiver"
    NSNR = "many_senders_many_receivers"
    NET_SETTLEMENT = "net_settlement_with_cycles"


class Observer(str, Enum):
    EXTERNAL = "external_onchain_observer"
    COUNTERPARTY = "protocol_counterparty"


@dataclass(frozen=True)
class OnChainObservation:
    inputs: tuple[int, ...]
    outputs: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.inputs or not self.outputs:
            raise ValueError("on-chain observation requires inputs and outputs")
        if any(value <= 0 for value in self.inputs + self.outputs):
            raise ValueError("on-chain amounts must be positive")
        if sum(self.outputs) > sum(self.inputs):
            raise ValueError("outputs cannot exceed inputs")


@dataclass(frozen=True)
class FormContract:
    form: CollaborativeForm
    participants: int | None
    observation: OnChainObservation
    transport: str
    external_knowledge: tuple[str, ...]
    counterparty_knowledge: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.participants is not None and self.participants < 1:
            raise ValueError("participant count must be positive when known")
        if not self.transport or not self.external_knowledge or not self.limitations:
            raise ValueError("form contract metadata must not be empty")


TWO_PARTY_OBSERVATION = OnChainObservation((90, 60), (110, 40))


def form_matrix() -> tuple[FormContract, ...]:
    """Return protocol/form contracts using the CTP's representative amounts."""

    external_two_party = (
        "input and output amounts",
        "transaction shape and script-visible construction features",
        "participant allocation is not observed",
        "payment amount is not observed",
    )
    counterparty_two_party = (
        "own inputs and outputs",
        "the only other party's remaining inputs and outputs by elimination",
        "negotiated payment amount",
    )
    two_party_limit = (
        "the same on-chain observation is compatible with an ordinary single-owner spend",
        "two-party PayJoin does not provide privacy from the counterparty",
    )
    rows = [
        FormContract(
            CollaborativeForm.ORDINARY_TWO_INPUT,
            1,
            TWO_PARTY_OBSERVATION,
            "ordinary wallet transaction",
            external_two_party,
            (),
            ("ownership is latent even when the transaction is actually unilateral",),
        )
    ]
    for form, transport in (
        (CollaborativeForm.P2EP, "Pay-to-EndPoint negotiation"),
        (CollaborativeForm.BIP79, "Bustapay template negotiation"),
        (CollaborativeForm.BIP78, "synchronous PayJoin negotiation"),
        (CollaborativeForm.BIP77, "asynchronous PayJoin negotiation"),
    ):
        rows.append(
            FormContract(
                form,
                2,
                TWO_PARTY_OBSERVATION,
                transport,
                external_two_party,
                counterparty_two_party,
                two_party_limit,
            )
        )
    rows.extend(
        (
            FormContract(
                CollaborativeForm.NS1R,
                4,
                OnChainObservation((40, 50, 60, 90), (160, 30, 30, 20)),
                "many senders negotiate with one receiver",
                ("amounts and transaction shape", "sender allocation is not observed"),
                (
                    "the receiver knows each negotiated payment and sender change",
                    "the receiver may not know which input belongs to which sender",
                ),
                (
                    "receiver consolidation and sibling-output spending can create fingerprints",
                ),
            ),
            FormContract(
                CollaborativeForm.NSNR,
                6,
                OnChainObservation(
                    (90, 15, 40, 30, 45, 35),
                    (85, 25, 50, 40, 45, 10),
                ),
                "paired many-sender many-receiver negotiation",
                ("amounts and transaction shape", "payment pairing is not observed"),
                ("own subtransaction and negotiated payment", "other pairings remain latent"),
                ("one payment per subtransaction leaves amount-based plausibility signals",),
            ),
            FormContract(
                CollaborativeForm.NET_SETTLEMENT,
                None,
                OnChainObservation((60, 20, 50), (40, 50, 40)),
                "multiparty settlement of mutual obligations",
                ("net on-chain balances", "participant count may remain latent"),
                ("own obligations and contributions", "other parties' gross obligations remain latent"),
                (
                    "cycles make gross payment amounts and obligation count unidentifiable",
                    "community structure and auxiliary information remain observable over time",
                ),
            ),
        )
    )
    return tuple(rows)


def knowledge(contract: FormContract, observer: Observer) -> tuple[str, ...]:
    """Return only the knowledge available to the declared observer."""

    if observer is Observer.EXTERNAL:
        return contract.external_knowledge
    if observer is Observer.COUNTERPARTY:
        return contract.counterparty_knowledge
    raise TypeError("observer must be an Observer")

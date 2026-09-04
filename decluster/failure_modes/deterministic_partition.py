"""Amount links shared by every exact non-derived subtransaction mapping."""

from __future__ import annotations

from ..baselines.maurer import exact_non_derived_mappings
from ..domain import (
    AttackReport,
    ConditionalLinksMeasured,
    EvidenceChannel,
    EvidenceContext,
    Subject,
    SubjectKind,
    UnanimousMappingLinksEvidence,
)


def evaluate(inputs, outputs, *, max_coins=12) -> AttackReport:
    """Enumerate Maurer's exact non-derived family and return unanimous links.

    The result is conditional on exact per-block conservation and equal weight
    across the retained family. It is not a model-independent ownership claim.
    """
    input_values = tuple(inputs)
    output_values = tuple(outputs)
    mappings = exact_non_derived_mappings(
        input_values, output_values, max_coins=max_coins
    )
    if not mappings:
        raise ValueError("fixture has no exact non-derived mapping")
    input_subjects = tuple(
        Subject(SubjectKind.COIN, ("input", index))
        for index in range(len(input_values))
    )
    output_subjects = tuple(
        Subject(SubjectKind.COIN, ("output", index))
        for index in range(len(output_values))
    )
    unanimous = []
    for input_index, input_subject in enumerate(input_subjects):
        for output_index, output_subject in enumerate(output_subjects):
            if all(
                any(
                    input_index in input_block and output_index in output_block
                    for input_block, output_block in mapping.blocks
                )
                for mapping in mappings
            ):
                unanimous.append((input_subject, output_subject))
    context = EvidenceContext(
        adversary="external observer using transaction amounts",
        observables=("input amounts", "output amounts"),
        hypothesis="inputs and outputs sharing a participant block are linked",
        algorithm="Maurer exact non-derived subtransaction mappings",
        dataset="CTP amount-partition examples scaled to integer units",
        limitations=(
            "every participant block must conserve value exactly",
            "fees and net-settlement cycles are outside this mapping model",
        ),
    )
    evidence = UnanimousMappingLinksEvidence(
        inputs=input_subjects,
        outputs=output_subjects,
        mapping_count=len(mappings),
        links=tuple(unanimous),
        context=context,
    )
    return AttackReport(
        identifier="deterministic-partition",
        attack="amount-constrained subtransaction partitioning",
        subjects=input_subjects + output_subjects,
        channels=(EvidenceChannel("exact_non_derived_mappings", (evidence,)),),
        outcomes=(ConditionalLinksMeasured(evidence),),
        limitations=(
            "certainty applies only within the declared exact non-derived mapping family",
            "the examples are scaled integer renderings of the CTP amount fixtures",
            "fees, contextual priors and net-settlement cycles are not modeled",
            "unanimous mapping links are not ownership attribution",
        ),
    )

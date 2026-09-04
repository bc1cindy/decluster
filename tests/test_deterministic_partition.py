import pytest

from decluster.domain import ConditionalLinksMeasured, UnanimousMappingLinksEvidence
from decluster.failure_modes.deterministic_partition import evaluate


def test_forced_ctp_example_has_one_mapping_and_four_unanimous_links():
    report = evaluate((1, 3, 20, 50), (4, 70))
    evidence = report.channels[0].evidence[0]
    assert isinstance(evidence, UnanimousMappingLinksEvidence)
    assert evidence.mapping_count == 1
    assert {(left.identifier, right.identifier) for left, right in evidence.links} == {
        (("input", 0), ("output", 0)),
        (("input", 1), ("output", 0)),
        (("input", 2), ("output", 1)),
        (("input", 3), ("output", 1)),
    }
    assert isinstance(report.outcomes[0], ConditionalLinksMeasured)
    assert report.composition is None


def test_underdetermined_ctp_control_has_three_mappings_and_no_unanimous_link():
    evidence = evaluate((1, 2, 3, 4, 5), (7, 8)).channels[0].evidence[0]
    assert evidence.mapping_count == 3
    assert evidence.links == ()


def test_absent_exact_mapping_is_refused():
    with pytest.raises(ValueError, match="no exact"):
        evaluate((1, 2), (4,))


def test_result_declares_model_limitations():
    report = evaluate((1, 3, 20, 50), (4, 70))
    assert any("only within" in limitation for limitation in report.limitations)
    assert any("net-settlement" in limitation for limitation in report.limitations)

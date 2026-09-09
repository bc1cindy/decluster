import inspect
import json
from pathlib import Path

from decluster import ancestry
from decluster.adaptations import ancestry as ancestry_adapter
from decluster.experiments import ancestry_contract, intersection_fixture

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RUNS = (
    (ancestry_contract, "results/artifacts/ancestry-contract-v1.json"),
    (intersection_fixture, "results/artifacts/intersection-cluster-fixture-v1.json"),
)


def _default_oracle(function):
    return inspect.signature(function).parameters["link_oracle"].default


def test_library_entry_points_default_to_the_nominal_value_flow_oracle():
    for function in (
        ancestry.ancestry_signature,
        ancestry.ancestry_signature_and_truncation,
        ancestry.ancestry_entropy,
    ):
        assert _default_oracle(function) is ancestry.value_flow_link_oracle


def test_the_adapter_delegates_the_default_instead_of_binding_a_second_one():
    assert _default_oracle(ancestry_adapter.ancestry_signature_report) is None


def test_canonical_runs_name_the_oracle_instead_of_inheriting_it():
    for experiment, artifact in CANONICAL_RUNS:
        assert experiment.ORACLE is ancestry.value_flow_link_oracle
        stored = json.loads((ROOT / artifact).read_text())
        assert stored["oracle"] == "decluster.ancestry.value_flow_link_oracle"
        experiment.verify_artifact(stored)

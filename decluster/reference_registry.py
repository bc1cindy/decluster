"""Strict readers for the CTP source and claim registries.

The registries are audit inputs, not free-form documentation.  Rejecting unknown
fields and dangling references prevents a typo from silently removing a source
from the fidelity matrix.
"""

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class RegistryError(ValueError):
    """The registry cannot support an auditable claim graph."""


class SourceKind(str, Enum):
    PAPER = "paper"
    PROTOCOL = "protocol"
    IMPLEMENTATION = "implementation"
    INFORMAL = "informal"
    INTERNAL_NOTE = "internal_note"


class Obligation(str, Enum):
    BASELINE = "baseline"
    FIXTURE = "fixture"
    METRIC = "metric"
    CONTEXT = "context"
    QUALIFICATION = "qualification"
    NO_CODE = "no_code_required"


class ClaimScope(str, Enum):
    FAILURE_MODE = "qualitative_failure_mode"
    MODEL_LIMIT = "model_limit"
    DEFENSIVE_CRITERION = "defensive_criterion"


class EvidenceLevel(str, Enum):
    UNIT_FIXTURE = "unit_fixture"
    PAPER_EXAMPLE = "paper_example"
    SYNTHETIC = "synthetic_experiment"
    PUBLISHED_DATASET = "published_dataset_reproduction"
    BITCOIN_SNAPSHOT = "bitcoin_snapshot_experiment"
    INDEPENDENT = "independent_replication"


class ClaimStatus(str, Enum):
    UNASSESSED = "unassessed"
    PARTIAL = "partially_supported"
    SUPPORTED_AT_LEVEL = "supported_at_evidence_level"
    NO_CODE = "no_code_required"


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    url: str | None
    kind: SourceKind
    obligation: Obligation
    note: str


@dataclass(frozen=True)
class Claim:
    id: str
    title: str
    scope: ClaimScope
    sources: tuple[str, ...]
    mechanism: str
    implementation: str | None
    evidence_level: EvidenceLevel
    status: ClaimStatus
    limitations: tuple[str, ...]


SOURCE_KEYS = frozenset({"id", "title", "url", "kind", "obligation", "note"})
CLAIM_KEYS = frozenset({
    "id", "title", "scope", "sources", "mechanism", "implementation",
    "evidence_level", "status", "limitations",
})


def _object(value, where):
    if not isinstance(value, dict):
        raise RegistryError(f"{where}: expected object")
    return value


def _exact_keys(value, expected, where):
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise RegistryError(f"{where}: missing={missing}, unknown={unknown}")


def _text(value, where, *, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"{where}: expected non-empty string")
    return value


def _enum(enum_type, value, where):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise RegistryError(f"{where}: invalid {enum_type.__name__}: {value!r}") from exc


def _load(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"{path}: cannot read registry: {exc}") from exc


def load_sources(path):
    root = _object(_load(path), str(path))
    _exact_keys(root, frozenset({"schema_version", "ctp_revision", "sources"}), str(path))
    if root["schema_version"] != 1:
        raise RegistryError(f"{path}: unsupported schema_version {root['schema_version']!r}")
    _text(root["ctp_revision"], f"{path}.ctp_revision")
    if not isinstance(root["sources"], list):
        raise RegistryError(f"{path}.sources: expected array")

    sources = []
    seen = set()
    for index, raw in enumerate(root["sources"]):
        where = f"{path}.sources[{index}]"
        raw = _object(raw, where)
        _exact_keys(raw, SOURCE_KEYS, where)
        source_id = _text(raw["id"], f"{where}.id")
        if source_id in seen:
            raise RegistryError(f"{where}.id: duplicate {source_id!r}")
        seen.add(source_id)
        url = _text(raw["url"], f"{where}.url", nullable=True)
        if url is not None and not url.startswith("https://"):
            raise RegistryError(f"{where}.url: expected https URL")
        sources.append(Source(
            id=source_id,
            title=_text(raw["title"], f"{where}.title"),
            url=url,
            kind=_enum(SourceKind, raw["kind"], f"{where}.kind"),
            obligation=_enum(Obligation, raw["obligation"], f"{where}.obligation"),
            note=_text(raw["note"], f"{where}.note"),
        ))
    return tuple(sources)


def load_claims(path, source_ids):
    root = _object(_load(path), str(path))
    _exact_keys(root, frozenset({"schema_version", "claims"}), str(path))
    if root["schema_version"] != 1:
        raise RegistryError(f"{path}: unsupported schema_version {root['schema_version']!r}")
    if not isinstance(root["claims"], list):
        raise RegistryError(f"{path}.claims: expected array")

    known_sources = set(source_ids)
    claims = []
    seen = set()
    for index, raw in enumerate(root["claims"]):
        where = f"{path}.claims[{index}]"
        raw = _object(raw, where)
        _exact_keys(raw, CLAIM_KEYS, where)
        claim_id = _text(raw["id"], f"{where}.id")
        if claim_id in seen:
            raise RegistryError(f"{where}.id: duplicate {claim_id!r}")
        seen.add(claim_id)
        if not isinstance(raw["sources"], list) or not raw["sources"]:
            raise RegistryError(f"{where}.sources: expected non-empty array")
        sources = tuple(_text(item, f"{where}.sources") for item in raw["sources"])
        dangling = sorted(set(sources) - known_sources)
        if dangling:
            raise RegistryError(f"{where}.sources: unknown source ids {dangling}")
        if len(sources) != len(set(sources)):
            raise RegistryError(f"{where}.sources: duplicate source id")
        if not isinstance(raw["limitations"], list):
            raise RegistryError(f"{where}.limitations: expected array")
        claims.append(Claim(
            id=claim_id,
            title=_text(raw["title"], f"{where}.title"),
            scope=_enum(ClaimScope, raw["scope"], f"{where}.scope"),
            sources=sources,
            mechanism=_text(raw["mechanism"], f"{where}.mechanism"),
            implementation=_text(raw["implementation"], f"{where}.implementation", nullable=True),
            evidence_level=_enum(EvidenceLevel, raw["evidence_level"], f"{where}.evidence_level"),
            status=_enum(ClaimStatus, raw["status"], f"{where}.status"),
            limitations=tuple(_text(item, f"{where}.limitations") for item in raw["limitations"]),
        ))
    return tuple(claims)

"""Typed, strict manifests for reproducible datasets and experiment runs.

These readers validate identities and lineage at the boundary.  They do not
download data, inspect the network, or silently repair incomplete manifests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping


class ManifestError(ValueError):
    """A manifest is incomplete, ambiguous, or internally inconsistent."""


class DatasetKind(str, Enum):
    FIXTURE = "git_fixture"
    SNAPSHOT = "immutable_snapshot"
    REGENERABLE = "regenerable"
    DERIVED = "derived"


class Redistribution(str, Enum):
    ALLOWED = "allowed"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class Sensitivity(str, Enum):
    SYNTHETIC = "synthetic"
    PUBLIC_ON_CHAIN = "public_on_chain"
    PUBLIC_AUXILIARY = "public_auxiliary"
    RESTRICTED_AUXILIARY = "restricted_auxiliary"


class ReproducibilityLevel(str, Enum):
    VERIFIED = "verified"
    REEXECUTABLE = "reexecutable"
    BITWISE = "bitwise_reproducible"
    STATISTICAL = "statistically_reproducible"


class RunAvailability(str, Enum):
    COMPLETE = "complete"
    RESTRICTED = "restricted"
    PARTIAL = "partial"


class VerificationMode(str, Enum):
    EXACT = "exact"
    TOLERANCE = "tolerance"
    STATISTICAL = "statistical"


@dataclass(frozen=True)
class ContentIdentity:
    bytes: int
    sha256: str


@dataclass(frozen=True)
class DatasetManifest:
    id: str
    title: str
    kind: DatasetKind
    schema: str
    format: str
    content: ContentIdentity
    local_path: str
    canonical_location: str | None
    mirrors: tuple[str, ...]
    provider: str
    snapshot_time: str | None
    recipe: str | None
    recipe_sha256: str | None
    data_license: str
    recipe_license: str | None
    redistribution: Redistribution
    sensitivity: Sensitivity
    code_revision: str | None
    parameters: Mapping
    parents: tuple[str, ...]
    ordering: str
    rng_algorithm: str | None
    rng_seed: int | None


@dataclass(frozen=True)
class DatasetInput:
    id: str
    sha256: str


@dataclass(frozen=True)
class DependencyInput:
    name: str
    version: str
    source: str
    revision: str
    lock_sha256: str | None
    license: str
    redistribution: Redistribution
    editable: bool


@dataclass(frozen=True)
class RunOutput:
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class RunVerification:
    mode: VerificationMode
    argv: tuple[str, ...]
    tests: tuple[str, ...]
    properties: tuple[str, ...]
    tolerance: str | None


@dataclass(frozen=True)
class RunManifest:
    id: str
    claim_ids: tuple[str, ...]
    code_revision: str
    dirty: bool
    argv: tuple[str, ...]
    python: str
    lock_digest: str | None
    platform: str
    dependencies: tuple[DependencyInput, ...]
    datasets: tuple[DatasetInput, ...]
    parameters: Mapping
    rng_algorithm: str | None
    rng_seeds: tuple[int, ...]
    outputs: tuple[RunOutput, ...]
    reproducibility_level: ReproducibilityLevel
    availability: RunAvailability
    verification: RunVerification
    limitations: tuple[str, ...]


DATASET_KEYS = frozenset({
    "schema_version", "id", "title", "kind", "schema", "format", "content",
    "locations", "source", "license", "redistribution", "sensitivity",
    "normalization", "determinism",
})
RUN_KEYS = frozenset({
    "schema_version", "id", "claim_ids", "code", "command", "environment",
    "datasets", "parameters", "rng", "outputs", "reproducibility", "verification",
    "limitations",
})
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _load(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{path}: cannot read manifest: {exc}") from exc


def _object(value, where, keys=None):
    if not isinstance(value, dict):
        raise ManifestError(f"{where}: expected object")
    if keys is not None and frozenset(value) != frozenset(keys):
        expected = frozenset(keys)
        actual = frozenset(value)
        raise ManifestError(
            f"{where}: missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )
    return value


def _text(value, where, *, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{where}: expected non-empty string")
    return value


def _https(value, where):
    value = _text(value, where, nullable=True)
    if value is not None and not value.startswith("https://"):
        raise ManifestError(f"{where}: expected https URL")
    return value


def _integer(value, where, *, minimum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(f"{where}: expected integer")
    if minimum is not None and value < minimum:
        raise ManifestError(f"{where}: expected value >= {minimum}")
    return value


def _digest(value, where, *, nullable=False):
    value = _text(value, where, nullable=nullable)
    if value is not None and not SHA256.fullmatch(value):
        raise ManifestError(f"{where}: expected lowercase SHA-256")
    return value


def _relative_path(value, where):
    value = _text(value, where)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path == Path("."):
        raise ManifestError(f"{where}: expected a safe relative path")
    return value


def _enum(enum_type, value, where):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"{where}: invalid {enum_type.__name__}: {value!r}") from exc


def _strings(value, where, *, nonempty=False, unique=False):
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise ManifestError(f"{where}: expected {qualifier}array")
    result = tuple(_text(item, f"{where}[{index}]") for index, item in enumerate(value))
    if unique and len(result) != len(set(result)):
        raise ManifestError(f"{where}: duplicate value")
    return result


def _array(value, where):
    if not isinstance(value, list):
        raise ManifestError(f"{where}: expected array")
    return value


def _freeze_json(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def load_dataset_manifest(path):
    where = str(path)
    raw = _object(_load(path), where, DATASET_KEYS)
    if raw["schema_version"] != 1:
        raise ManifestError(f"{where}: unsupported schema_version {raw['schema_version']!r}")

    content = _object(raw["content"], f"{where}.content", {"bytes", "sha256"})
    locations = _object(
        raw["locations"], f"{where}.locations", {"local_path", "canonical", "mirrors"}
    )
    source = _object(
        raw["source"], f"{where}.source",
        {"provider", "snapshot_time", "recipe", "recipe_sha256"},
    )
    license_ = _object(raw["license"], f"{where}.license", {"data", "recipe"})
    normalization = _object(
        raw["normalization"], f"{where}.normalization",
        {"code_revision", "parameters", "parents"},
    )
    determinism = _object(
        raw["determinism"], f"{where}.determinism",
        {"ordering", "rng_algorithm", "rng_seed"},
    )
    mirrors = _strings(locations["mirrors"], f"{where}.locations.mirrors", unique=True)
    for index, mirror in enumerate(mirrors):
        _https(mirror, f"{where}.locations.mirrors[{index}]")
    parameters = _object(normalization["parameters"], f"{where}.normalization.parameters")
    rng_seed = determinism["rng_seed"]
    if rng_seed is not None:
        rng_seed = _integer(rng_seed, f"{where}.determinism.rng_seed", minimum=0)

    manifest = DatasetManifest(
        id=_text(raw["id"], f"{where}.id"),
        title=_text(raw["title"], f"{where}.title"),
        kind=_enum(DatasetKind, raw["kind"], f"{where}.kind"),
        schema=_text(raw["schema"], f"{where}.schema"),
        format=_text(raw["format"], f"{where}.format"),
        content=ContentIdentity(
            bytes=_integer(content["bytes"], f"{where}.content.bytes", minimum=0),
            sha256=_digest(content["sha256"], f"{where}.content.sha256"),
        ),
        local_path=_text(locations["local_path"], f"{where}.locations.local_path"),
        canonical_location=_https(locations["canonical"], f"{where}.locations.canonical"),
        mirrors=mirrors,
        provider=_text(source["provider"], f"{where}.source.provider"),
        snapshot_time=_text(source["snapshot_time"], f"{where}.source.snapshot_time", nullable=True),
        recipe=_text(source["recipe"], f"{where}.source.recipe", nullable=True),
        recipe_sha256=_digest(source["recipe_sha256"], f"{where}.source.recipe_sha256", nullable=True),
        data_license=_text(license_["data"], f"{where}.license.data"),
        recipe_license=_text(license_["recipe"], f"{where}.license.recipe", nullable=True),
        redistribution=_enum(Redistribution, raw["redistribution"], f"{where}.redistribution"),
        sensitivity=_enum(Sensitivity, raw["sensitivity"], f"{where}.sensitivity"),
        code_revision=_text(normalization["code_revision"], f"{where}.normalization.code_revision", nullable=True),
        parameters=_freeze_json(parameters),
        parents=_strings(normalization["parents"], f"{where}.normalization.parents", unique=True),
        ordering=_text(determinism["ordering"], f"{where}.determinism.ordering"),
        rng_algorithm=_text(determinism["rng_algorithm"], f"{where}.determinism.rng_algorithm", nullable=True),
        rng_seed=rng_seed,
    )
    if manifest.kind is DatasetKind.DERIVED and not manifest.parents:
        raise ManifestError(f"{where}: derived dataset must name at least one parent")
    if manifest.recipe_sha256 is not None and manifest.recipe is None:
        raise ManifestError(f"{where}: recipe_sha256 requires recipe")
    if manifest.rng_seed is not None and manifest.rng_algorithm is None:
        raise ManifestError(f"{where}: rng_seed requires rng_algorithm")
    return manifest


def load_run_manifest(path, *, claim_ids, datasets):
    where = str(path)
    raw = _object(_load(path), where, RUN_KEYS)
    if raw["schema_version"] != 1:
        raise ManifestError(f"{where}: unsupported schema_version {raw['schema_version']!r}")
    code = _object(raw["code"], f"{where}.code", {"revision", "dirty"})
    command = _object(raw["command"], f"{where}.command", {"argv"})
    environment = _object(
        raw["environment"], f"{where}.environment",
        {"python", "lock_digest", "platform", "dependencies"},
    )
    rng = _object(raw["rng"], f"{where}.rng", {"algorithm", "seeds"})
    reproducibility = _object(
        raw["reproducibility"], f"{where}.reproducibility", {"level", "availability"}
    )
    verification = _object(
        raw["verification"], f"{where}.verification",
        {"mode", "argv", "tests", "properties", "tolerance"},
    )
    if not isinstance(code["dirty"], bool):
        raise ManifestError(f"{where}.code.dirty: expected boolean")
    dependencies = []
    dependency_names = set()
    for index, item in enumerate(_array(environment["dependencies"], f"{where}.environment.dependencies")):
        item_where = f"{where}.environment.dependencies[{index}]"
        item = _object(item, item_where, {
            "name", "version", "source", "revision", "lock_sha256", "license",
            "redistribution", "editable",
        })
        name = _text(item["name"], f"{item_where}.name")
        if name in dependency_names:
            raise ManifestError(f"{item_where}.name: duplicate {name!r}")
        dependency_names.add(name)
        if not isinstance(item["editable"], bool):
            raise ManifestError(f"{item_where}.editable: expected boolean")
        dependencies.append(DependencyInput(
            name=name,
            version=_text(item["version"], f"{item_where}.version"),
            source=_https(item["source"], f"{item_where}.source"),
            revision=_text(item["revision"], f"{item_where}.revision"),
            lock_sha256=_digest(item["lock_sha256"], f"{item_where}.lock_sha256", nullable=True),
            license=_text(item["license"], f"{item_where}.license"),
            redistribution=_enum(Redistribution, item["redistribution"], f"{item_where}.redistribution"),
            editable=item["editable"],
        ))
    run_claims = _strings(raw["claim_ids"], f"{where}.claim_ids", nonempty=True, unique=True)
    dangling_claims = sorted(set(run_claims) - set(claim_ids))
    if dangling_claims:
        raise ManifestError(f"{where}.claim_ids: unknown claim ids {dangling_claims}")

    inputs = []
    seen_inputs = set()
    for index, item in enumerate(_array(raw["datasets"], f"{where}.datasets")):
        item_where = f"{where}.datasets[{index}]"
        item = _object(item, item_where, {"id", "sha256"})
        dataset_id = _text(item["id"], f"{item_where}.id")
        if dataset_id in seen_inputs:
            raise ManifestError(f"{item_where}.id: duplicate {dataset_id!r}")
        seen_inputs.add(dataset_id)
        digest = _digest(item["sha256"], f"{item_where}.sha256")
        expected = datasets.get(dataset_id)
        if expected is None:
            raise ManifestError(f"{item_where}.id: unknown dataset {dataset_id!r}")
        if expected.content.sha256 != digest:
            raise ManifestError(f"{item_where}.sha256: does not match dataset manifest")
        inputs.append(DatasetInput(dataset_id, digest))

    outputs = []
    seen_outputs = set()
    for index, item in enumerate(_array(raw["outputs"], f"{where}.outputs")):
        item_where = f"{where}.outputs[{index}]"
        item = _object(item, item_where, {"path", "bytes", "sha256"})
        output_path = _relative_path(item["path"], f"{item_where}.path")
        if output_path in seen_outputs:
            raise ManifestError(f"{item_where}.path: duplicate {output_path!r}")
        seen_outputs.add(output_path)
        outputs.append(RunOutput(
            path=output_path,
            bytes=_integer(item["bytes"], f"{item_where}.bytes", minimum=0),
            sha256=_digest(item["sha256"], f"{item_where}.sha256"),
        ))
    if not outputs:
        raise ManifestError(f"{where}.outputs: expected non-empty array")

    seeds = rng["seeds"]
    if not isinstance(seeds, list):
        raise ManifestError(f"{where}.rng.seeds: expected array")
    seeds = tuple(_integer(seed, f"{where}.rng.seeds", minimum=0) for seed in seeds)
    algorithm = _text(rng["algorithm"], f"{where}.rng.algorithm", nullable=True)
    if seeds and algorithm is None:
        raise ManifestError(f"{where}.rng: seeds require algorithm")

    level = _enum(
        ReproducibilityLevel, reproducibility["level"],
        f"{where}.reproducibility.level",
    )
    availability = _enum(
        RunAvailability, reproducibility["availability"],
        f"{where}.reproducibility.availability",
    )
    mode = _enum(VerificationMode, verification["mode"], f"{where}.verification.mode")
    verification_argv = _strings(
        verification["argv"], f"{where}.verification.argv", nonempty=True
    )
    verification_tests = _strings(
        verification["tests"], f"{where}.verification.tests", unique=True
    )
    verification_properties = _strings(
        verification["properties"], f"{where}.verification.properties", unique=True
    )
    if not verification_tests and not verification_properties:
        raise ManifestError(
            f"{where}.verification: expected at least one test or property"
        )
    tolerance = _text(
        verification["tolerance"], f"{where}.verification.tolerance", nullable=True
    )
    if mode is VerificationMode.EXACT and tolerance is not None:
        raise ManifestError(f"{where}.verification: exact mode forbids tolerance")
    if mode is not VerificationMode.EXACT and tolerance is None:
        raise ManifestError(f"{where}.verification: {mode.value} mode requires tolerance")
    if level is ReproducibilityLevel.BITWISE and mode is not VerificationMode.EXACT:
        raise ManifestError(
            f"{where}.reproducibility: bitwise reproducibility requires exact verification"
        )
    if level is ReproducibilityLevel.STATISTICAL and mode is not VerificationMode.STATISTICAL:
        raise ManifestError(
            f"{where}.reproducibility: statistical reproducibility requires statistical verification"
        )

    return RunManifest(
        id=_text(raw["id"], f"{where}.id"),
        claim_ids=run_claims,
        code_revision=_text(code["revision"], f"{where}.code.revision"),
        dirty=code["dirty"],
        argv=_strings(command["argv"], f"{where}.command.argv", nonempty=True),
        python=_text(environment["python"], f"{where}.environment.python"),
        lock_digest=_digest(environment["lock_digest"], f"{where}.environment.lock_digest", nullable=True),
        platform=_text(environment["platform"], f"{where}.environment.platform"),
        dependencies=tuple(dependencies),
        datasets=tuple(inputs),
        parameters=_freeze_json(_object(raw["parameters"], f"{where}.parameters")),
        rng_algorithm=algorithm,
        rng_seeds=seeds,
        outputs=tuple(outputs),
        reproducibility_level=level,
        availability=availability,
        verification=RunVerification(
            mode=mode,
            argv=verification_argv,
            tests=verification_tests,
            properties=verification_properties,
            tolerance=tolerance,
        ),
        limitations=_strings(raw["limitations"], f"{where}.limitations"),
    )

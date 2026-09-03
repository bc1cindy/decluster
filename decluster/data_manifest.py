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
class RunOutput:
    path: str
    bytes: int
    sha256: str


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
    datasets: tuple[DatasetInput, ...]
    parameters: Mapping
    rng_algorithm: str | None
    rng_seeds: tuple[int, ...]
    outputs: tuple[RunOutput, ...]
    tolerance: str
    limitations: tuple[str, ...]


DATASET_KEYS = frozenset({
    "schema_version", "id", "title", "kind", "schema", "format", "content",
    "locations", "source", "license", "redistribution", "sensitivity",
    "normalization", "determinism",
})
RUN_KEYS = frozenset({
    "schema_version", "id", "claim_ids", "code", "command", "environment",
    "datasets", "parameters", "rng", "outputs", "metrics", "limitations",
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
        raw["environment"], f"{where}.environment", {"python", "lock_digest", "platform"}
    )
    rng = _object(raw["rng"], f"{where}.rng", {"algorithm", "seeds"})
    metrics = _object(raw["metrics"], f"{where}.metrics", {"tolerance"})
    if not isinstance(code["dirty"], bool):
        raise ManifestError(f"{where}.code.dirty: expected boolean")
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
    for index, item in enumerate(_array(raw["outputs"], f"{where}.outputs")):
        item_where = f"{where}.outputs[{index}]"
        item = _object(item, item_where, {"path", "bytes", "sha256"})
        outputs.append(RunOutput(
            path=_text(item["path"], f"{item_where}.path"),
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

    return RunManifest(
        id=_text(raw["id"], f"{where}.id"),
        claim_ids=run_claims,
        code_revision=_text(code["revision"], f"{where}.code.revision"),
        dirty=code["dirty"],
        argv=_strings(command["argv"], f"{where}.command.argv", nonempty=True),
        python=_text(environment["python"], f"{where}.environment.python"),
        lock_digest=_digest(environment["lock_digest"], f"{where}.environment.lock_digest", nullable=True),
        platform=_text(environment["platform"], f"{where}.environment.platform"),
        datasets=tuple(inputs),
        parameters=_freeze_json(_object(raw["parameters"], f"{where}.parameters")),
        rng_algorithm=algorithm,
        rng_seeds=seeds,
        outputs=tuple(outputs),
        tolerance=_text(metrics["tolerance"], f"{where}.metrics.tolerance"),
        limitations=_strings(raw["limitations"], f"{where}.limitations"),
    )

"""Inventory legacy result documents against executable run manifests."""

from dataclasses import dataclass
import json
from pathlib import Path


# Some historical documents summarize a narrower canonical run or share one
# with another document, so their names cannot be inferred from output stems.
DOCUMENT_RUN_ALIASES = {
    "RESULTS-analyze.md": "analyze-contract-v1",
    "RESULTS-ancestry.md": "ancestry-contract-v1",
    "RESULTS-conservation.md": "conservation-round-three-v1",
    "RESULTS-path-count.md": "path-count-contract-v1",
    "RESULTS-path-counting-analysis.md": "path-count-contract-v1",
    "RESULTS-slice-a-channels.md": "slice-channels-v1",
}


@dataclass(frozen=True)
class ResultInventoryEntry:
    document: str
    status: str
    legacy_manifest: str | None = None
    canonical_run: str | None = None


def _run_outputs(root: Path) -> dict[str, str]:
    owners = {}
    for path in sorted((root / "catalog" / "runs").glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        for output in value.get("outputs", []):
            owners[Path(output["path"]).name] = value["id"]
    return owners


def inventory_results(root: Path) -> tuple[ResultInventoryEntry, ...]:
    """Classify every legacy result without claiming unsupported provenance."""
    run_outputs = _run_outputs(root)
    generated_by_stem = {
        Path(name).stem.removesuffix("-v1"): run_id
        for name, run_id in run_outputs.items()
        if name.endswith(".md")
    }
    entries = []
    for document in sorted((root / "results").glob("RESULTS-*.md")):
        stem = document.stem.removeprefix("RESULTS-")
        old_manifest = root / "results" / "manifests" / f"{document.stem}.json"
        canonical_run = DOCUMENT_RUN_ALIASES.get(document.name, generated_by_stem.get(stem))
        if canonical_run is not None:
            status = "superseded_by_canonical_run"
        elif old_manifest.is_file():
            status = "legacy_manifest_requires_migration"
        else:
            status = "historical_result_without_run_manifest"
        entries.append(ResultInventoryEntry(
            document=str(document.relative_to(root)),
            status=status,
            legacy_manifest=(
                str(old_manifest.relative_to(root)) if old_manifest.is_file() else None
            ),
            canonical_run=canonical_run,
        ))
    return tuple(entries)


def summarize(entries: tuple[ResultInventoryEntry, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    return dict(sorted(counts.items()))

"""Build deterministic compressed snapshots of exact N-S Bitcoin windows."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import tempfile


def build_window(source, destination, *, minimum_height, maximum_height):
    """Copy records in an inclusive height range to deterministic gzip NDJSON."""
    if minimum_height > maximum_height:
        raise ValueError("minimum_height must not exceed maximum_height")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as raw:
        temporary = Path(raw.name)
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as target:
            with gzip.open(source, "rt", encoding="utf-8") as records:
                for line in records:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if minimum_height <= record.get("height", 0) <= maximum_height:
                        target.write(line.encode("utf-8"))
                        count += 1
    temporary.replace(destination)
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--minimum-height", type=int, required=True)
    parser.add_argument("--maximum-height", type=int, required=True)
    args = parser.parse_args(argv)
    count = build_window(
        args.source,
        args.destination,
        minimum_height=args.minimum_height,
        maximum_height=args.maximum_height,
    )
    print(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

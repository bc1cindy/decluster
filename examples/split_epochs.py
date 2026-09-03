"""Split monthly NDJSON epochs into seekable block-height chunks.

Each input is decompressed once. Outputs retain NDJSON gzip format so every existing reader can
consume them, while a multi-epoch run no longer rescans an entire month for each sub-window.

usage: python3 examples/split_epochs.py OUTPUT_DIR INPUT... [--blocks 1008]
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path


def _open(path, mode="rt"):
    return gzip.open(path, mode) if str(path).endswith(".gz") else open(path, mode)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def split_file(source, output_dir, blocks):
    stem = Path(source).name.removesuffix(".gz").removesuffix(".ndjson")
    writers = {}
    records = {}
    try:
        with _open(source) as incoming:
            for line in incoming:
                if not line.strip():
                    continue
                tx = json.loads(line)
                height = int(tx.get("height") or 0)
                bucket = height // blocks
                if bucket not in writers:
                    lo = bucket * blocks
                    hi = lo + blocks - 1
                    path = os.path.join(output_dir, f"{stem}_{lo}-{hi}.ndjson.gz")
                    writers[bucket] = gzip.open(path, "wt")
                    records[bucket] = {"source": str(source), "path": path,
                                       "height_lo": height, "height_hi": height,
                                       "transactions": 0}
                writers[bucket].write(line)
                record = records[bucket]
                record["height_lo"] = min(record["height_lo"], height)
                record["height_hi"] = max(record["height_hi"], height)
                record["transactions"] += 1
    finally:
        for writer in writers.values():
            writer.close()
    ordered = [records[bucket] for bucket in sorted(records)]
    for record in ordered:
        record["sha256"] = _sha256(record["path"])
    return ordered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--blocks", type=int, default=1008,
                        help="block heights per chunk (1008 is approximately one week)")
    args = parser.parse_args()
    if args.blocks <= 0:
        parser.error("--blocks must be positive")
    os.makedirs(args.output_dir, exist_ok=True)
    records = []
    for source in args.inputs:
        records.extend(split_file(source, args.output_dir, args.blocks))
    manifest = {"blocks_per_chunk": args.blocks, "chunks": records}
    manifest_path = os.path.join(args.output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"wrote {len(records)} chunks and {manifest_path}")


if __name__ == "__main__":
    main()

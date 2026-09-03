"""Download a wide BigQuery slice WITHOUT billing/GCS, by chunking into small block ranges that each
fit under the `bq query` download limit, then concatenating to one ndjson. For Collection A (wide
multi-epoch slices → social graph / def1). Free-tier query only (no bq extract, no bucket).

usage: python3 examples/bq_chunk_download.py <partition_month YYYY-MM-01> <lo> <hi> <chunk_blocks> <out.ndjson>
e.g.:  python3 examples/bq_chunk_download.py 2016-02-01 400000 400600 20 slice_a.ndjson
Resumable: appends; a re-run with the same out re-fetches only missing chunks (dedup by txid on load).
"""
import sys
import os
import json
import subprocess

TEMPLATE = """SELECT `hash` AS txid, block_number AS height,
  ARRAY(SELECT AS STRUCT STRUCT(i.addresses[SAFE_OFFSET(0)] AS scriptpubkey_address) AS prevout FROM UNNEST(inputs) AS i) AS vin,
  ARRAY(SELECT AS STRUCT o.addresses[SAFE_OFFSET(0)] AS scriptpubkey_address FROM UNNEST(outputs) AS o) AS vout
FROM `bigquery-public-data.crypto_bitcoin.transactions`
WHERE block_timestamp_month = '{month}' AND block_number BETWEEN {lo} AND {hi} AND NOT is_coinbase"""


def run_chunk(month, lo, hi):
    q = TEMPLATE.format(month=month, lo=lo, hi=hi)
    raw = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--format=json",
                          "--max_rows=500000", q], capture_output=True, text=True, timeout=110)
    if raw.returncode != 0:
        raise RuntimeError(raw.stderr[:200])
    return json.loads(raw.stdout) if raw.stdout.strip() else []


def main(month, lo, hi, chunk, out):
    seen = set()
    if os.path.exists(out):
        for line in open(out):
            try:
                seen.add(json.loads(line)["txid"])
            except Exception:
                pass
    print(f"resume: {len(seen)} txs already downloaded", flush=True)
    with open(out, "a") as f:
        b = lo
        while b <= hi:
            top = min(b + chunk - 1, hi)
            try:
                rows = run_chunk(month, b, top)
            except Exception as e:
                print(f"  blocks {b}-{top}: FAILED ({e}); shrink chunk if this repeats", flush=True)
                b = top + 1
                continue
            new = 0
            for r in rows:
                if r["txid"] in seen:
                    continue
                r["height"] = int(r["height"])
                f.write(json.dumps(r) + "\n")
                seen.add(r["txid"])
                new += 1
            f.flush()
            print(f"  blocks {b}-{top}: +{new} txs ({len(seen)} total)", flush=True)
            b = top + 1
    print(f"done: {len(seen)} txs in {out}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])

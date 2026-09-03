"""Download one contiguous month of the address-level tx graph WITHOUT billing, efficiently: one
BigQuery scan of the month partition into a destination table, then paginate the download from that
table with `bq head` (tabledata.list, free, no re-scan). This replaces the per-chunk downloader, whose
block-range filter still scans the whole month partition on every chunk.

usage: python3 examples/collect_month.py <YYYY-MM> <lo_block> <hi_block> <out.ndjson>
Emits {txid, height, vin:[{prevout:{scriptpubkey_address}}], vout:[{scriptpubkey_address}]} per line,
the shape the clustering/contraction reads. Resumable at month granularity (skips a complete file).
"""
import sys
import os
import json
import subprocess

TABLE = "decluster_scratch.epoch_tmp"
TEMPLATE = """SELECT `hash` AS txid, block_number AS height,
  ARRAY(SELECT AS STRUCT STRUCT(i.addresses[SAFE_OFFSET(0)] AS scriptpubkey_address) AS prevout FROM UNNEST(inputs) AS i) AS vin,
  ARRAY(SELECT AS STRUCT o.addresses[SAFE_OFFSET(0)] AS scriptpubkey_address FROM UNNEST(outputs) AS o) AS vout
FROM `bigquery-public-data.crypto_bitcoin.transactions`
WHERE block_timestamp_month = '{month}-01' AND block_number BETWEEN {lo} AND {hi} AND NOT is_coinbase"""


def materialize(month, lo, hi):
    q = TEMPLATE.format(month=month, lo=lo, hi=hi)
    r = subprocess.run(["bq", "query", "--use_legacy_sql=false", f"--destination_table={TABLE}",
                        "--replace=true", "--format=none", q], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:400])


def table_count():
    r = subprocess.run(["bq", "query", "--use_legacy_sql=false", "--format=csv",
                        f"SELECT COUNT(*) FROM {TABLE}"], capture_output=True, text=True, timeout=180)
    return int(r.stdout.strip().splitlines()[-1])


def page(offset, n, attempts=5):
    last = ""
    for i in range(attempts):
        try:
            r = subprocess.run(["bq", "head", "-n", str(n), "--start_row", str(offset),
                                "--format=json", TABLE], capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            last = "timeout"
            print(f"    page@{offset} timeout, retry {i + 1}/{attempts}", flush=True)
            continue
        if r.returncode != 0:
            last = r.stderr[:200]
            print(f"    page@{offset} err ({last}), retry {i + 1}/{attempts}", flush=True)
            continue
        return json.loads(r.stdout) if r.stdout.strip() else []
    raise RuntimeError(f"page@{offset} failed after {attempts}: {last}")


def main(month, lo, hi, out):
    print(f"materializing {month} blocks {lo}-{hi} (one scan)...", flush=True)
    materialize(month, lo, hi)
    total = table_count()
    print(f"  {total} rows materialized; paginating (free reads)...", flush=True)
    n, got = 25000, 0
    with open(out, "w") as f:
        while got < total:
            rows = page(got, n)
            if not rows:
                break
            for r in rows:
                r["height"] = int(r["height"])
                f.write(json.dumps(r) + "\n")
            got += len(rows)
            f.flush()
            print(f"  {got}/{total}", flush=True)
    print(f"done: {got} txs in {out}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])

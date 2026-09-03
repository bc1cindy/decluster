"""Collect the twelve contiguous monthly epochs of 2016 for the multi-epoch cross-view test, one
`collect_month` run each (one BigQuery scan per month, free paginated download). Month-level resume:
a completed month writes an `<out>.done` marker and is skipped on restart, so an interrupted or
quota-paused run continues where it left off (the free-tier scan budget resets monthly).

usage: python3 examples/collect_2016_epochs.py [out_dir]
"""
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from examples.collect_month import main as collect_month

# (month, lo_block, hi_block) from MIN/MAX block_number per 2016 month partition
MONTHS = [
    ("2016-01", 391182, 396048), ("2016-02", 396049, 400600), ("2016-03", 400601, 405178),
    ("2016-04", 405179, 409637), ("2016-05", 409638, 414257), ("2016-06", 414258, 418722),
    ("2016-07", 418723, 423087), ("2016-08", 423088, 427736), ("2016-09", 427737, 432283),
    ("2016-10", 432284, 436827), ("2016-11", 436828, 441340), ("2016-12", 441341, 446032),
]


def main(out_dir="."):
    for month, lo, hi in MONTHS:
        out = os.path.join(out_dir, f"epoch_{month.replace('-', '_')}.ndjson")
        if os.path.exists(out + ".done"):
            print(f"[{month}] already complete, skipping", flush=True)
            continue
        print(f"[{month}] collecting -> {out}", flush=True)
        collect_month(month, lo, hi, out)
        subprocess.run(["gzip", "-f", out])          # compress in place (~5x); analysis reads .gz
        print(f"[{month}] compressed -> {out}.gz", flush=True)
        open(out + ".done", "w").close()
    print("all epochs collected", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")

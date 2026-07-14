"""Measure per-axis fingerprint bits on real samples, and load exported tx data.
Subcommands: file (measure a BigQuery NDJSON/array export), sample (large mempool sample),
recalibrate (unbiased mainnet sample), chainprove (witness axes + chain-proven examples).
usage: python3 -m decluster.measure <file|sample|recalibrate|chainprove> [args]"""
import sys, json
from .engine import measure, print_report, locktime_class
from .sampling import sample_chain_uniform
from .fetch import fetch_tx
from .extractors import (
    x_nsequence, x_input_order, x_io_shape, x_version, x_output_order, x_change_spk_type,
    x_uih, x_low_r, x_sighash, x_fee_rate, x_input_script_type, x_op_return, x_output_encoding,
    x_input_types_present, x_nested_segwit, x_pubkey_compression, x_multisig,
    x_change_index, x_change_type_match, x_change_matches_output, x_change_address_reuse,
)

# Full 22-axis map (mempool sample carries witness; BigQuery reads 'na' on witness axes).
EX = {
    "nsequence": lambda t: x_nsequence(t), "locktime": locktime_class,
    "input_order": lambda t: x_input_order(t), "output_order": lambda t: x_output_order(t),
    "change_spk": lambda t: x_change_spk_type(t), "version": lambda t: x_version(t),
    "io_shape": lambda t: x_io_shape(t), "uih": lambda t: x_uih(t),
    "low_r": lambda t: x_low_r(t), "sighash": lambda t: x_sighash(t),
    "fee_rate": lambda t: x_fee_rate(t), "input_script_type": lambda t: x_input_script_type(t),
    "op_return": lambda t: x_op_return(t), "output_encoding": lambda t: x_output_encoding(t),
    "input_types_present": lambda t: x_input_types_present(t), "nested_segwit": lambda t: x_nested_segwit(t),
    "pubkey_compression": lambda t: x_pubkey_compression(t), "multisig": lambda t: x_multisig(t),
    "change_index": lambda t: x_change_index(t), "change_type_match": lambda t: x_change_type_match(t),
    "change_matches_output": lambda t: x_change_matches_output(t),
    "change_address_reuse": lambda t: x_change_address_reuse(t),
}


def _int(x):
    try: return int(x)
    except (TypeError, ValueError): return x


def _unwrap(obj):
    # BigQuery exports the `row` column as a JSON string; unwrap it
    if isinstance(obj, dict) and set(obj.keys()) == {"row"}:
        return json.loads(obj["row"])
    return obj


def _coerce(tx):
    # BigQuery exports INT64 as JSON strings -> coerce numeric fields back to int
    for k in ("height", "version", "locktime", "fee", "weight"):
        if k in tx: tx[k] = _int(tx[k])
    for v in tx.get("vin", []) or []:
        for k in ("vout", "sequence", "value"):
            if k in v: v[k] = _int(v[k])
        pv = v.get("prevout")
        if isinstance(pv, dict) and "value" in pv: pv["value"] = _int(pv["value"])
    for o in tx.get("vout", []) or []:
        if "value" in o: o["value"] = _int(o["value"])
    return tx


def load_ndjson(path):
    """Accepts NDJSON or a JSON array — the BigQuery console downloads either."""
    raw = open(path).read().strip()
    rows = json.loads(raw) if raw.startswith("[") else [json.loads(l) for l in raw.splitlines() if l.strip()]
    return [(_coerce(_unwrap(r)), _coerce(_unwrap(r)).get("height")) for r in rows]


def _measure_files(paths):
    seen, sample = set(), []
    for path in paths:
        for tx, h in load_ndjson(path):
            if tx.get("txid") in seen: continue
            seen.add(tx.get("txid")); sample.append((tx, h))
    print(f"# combined sample: {len(sample)} unique txs from {len(paths)} file(s)")
    print_report(measure(sample, EX))


def _chainprove():
    catalog = [("Ex.1 low-R", "8dba6657ab9bb44824b3317c8cc3f333c2f465d3668c678691a091cdd6e5984c", x_low_r),
               ("Ex.2 sighash", "3c5436f1edf7d4c32a5ccf2448c1e963f52bb8a0fb6f8688d7e78a14e1cbe80b", x_sighash)]
    print("== catalog txids (verification) ==")
    for label, txid, fn in catalog:
        try: print(f"{label} {txid[:12]}.. -> {fn(fetch_tx(txid))}")
        except Exception as e: print(f"{label} {txid[:12]}.. UNVERIFIABLE ({e})")
    sample = sample_chain_uniform(n_blocks=40, per_block=8, seed=0)
    print(f"\n# witness-axis bits over {len(sample)} txs")
    print_report(measure(sample, {"low_r": lambda t: x_low_r(t), "sighash": lambda t: x_sighash(t)}))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "file"
    if cmd == "file":
        _measure_files(sys.argv[2:])
    elif cmd in ("sample", "recalibrate"):
        n = int(sys.argv[2]) if len(sys.argv) > 2 else (200 if cmd == "sample" else 40)
        per = int(sys.argv[3]) if len(sys.argv) > 3 else (20 if cmd == "sample" else 25)
        s = sample_chain_uniform(n_blocks=n, per_block=per, seed=0)
        print(f"# {cmd}: {len(s)} txs over {n} blocks")
        print_report(measure(s, EX))
    elif cmd == "chainprove":
        _chainprove()
    else:
        print(f"unknown subcommand: {cmd}")

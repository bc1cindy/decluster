"""Bridge to the tx-indexer Rust engine. Three parts:
- vector(tx): replicates the CollectFingerprints 18-position u32 vector exactly, so bits
  measured here feed EvidenceModel::from_bits_json.
- calibrate/merge_witness: measure per-axis bits on samples -> rust_bits.json.
- score/evaluate: validate that the model ranks same-wallet tx pairs above random (AUC).
usage: python3 -m decluster.rust_bridge <calibrate <files> [--witness] | validate [blkcache]>"""
import sys, json, math, random, glob
from collections import Counter
from .extractors import x_nsequence, x_sighash
from .measure import load_ndjson
from .graph_deanon import auc

# --- schema: mirror heuristics/src/ast/fingerprint.rs ---
_NSEQ = {"cake_group_c": 0, "seq_0x01_other": 1, "rbf_fffffffd": 2,
         "final_fffffffe": 3, "max_ffffffff": 4, "mixed_other": 5}
_SIGHASH = {"taproot_default": 0, "taproot_explicit": 1, "all": 2, "none": 3, "single": 4,
            "anyonecanpay_all": 5, "anyonecanpay_none": 6, "anyonecanpay_single": 7,
            "mixed": 9, "na": 10}
_OUT_TYPE = {"p2pkh": 0, "pubkeyhash": 0, "p2sh": 1, "scripthash": 1,
             "v0_p2wpkh": 2, "witness_v0_keyhash": 2, "v0_p2wsh": 3, "witness_v0_scripthash": 3,
             "v1_p2tr": 4, "witness_v1_taproot": 4, "op_return": 5, "nulldata": 5}


def _otype(spk_type):
    return _OUT_TYPE.get(spk_type, 6)   # p2pk / multisig / unknown / nonstandard -> NonStandard


def _bitset(vals):
    """discriminant_bitset: OR of 1<<(v & 31)."""
    acc = 0
    for v in vals:
        acc |= 1 << (v & 31)
    return acc


def _seqs(tx):
    return [v.get("sequence", 0xFFFFFFFF) for v in tx["vin"]]


def _input_order(tx):
    """InputSortingType bitset: Single=0 Asc=1 Desc=2 Bip69=3 Unknown=5."""
    vin = tx["vin"]
    if len(vin) == 1:
        return _bitset([0])
    types = []
    amounts = [v.get("prevout", {}).get("value") for v in vin]
    if all(a is not None for a in amounts) and len(set(amounts)) > 1:
        if amounts == sorted(amounts): types.append(1)
        if amounts == sorted(amounts, reverse=True): types.append(2)
    outpoints = [(v["txid"], v.get("vout", 0)) for v in vin]
    if outpoints == sorted(outpoints, key=lambda o: (bytes.fromhex(o[0]), o[1])):
        types.append(3)
    if not types: types.append(5)
    return _bitset(types)


def _uih1(tx):
    in_vals = [v.get("prevout", {}).get("value") for v in tx["vin"]]
    in_vals = [x for x in in_vals if x is not None]
    out_vals = [o.get("value") for o in tx["vout"] if o.get("value") is not None]
    if len(in_vals) < 2 or not out_vals:
        return 0
    return int(max(in_vals) >= max(out_vals))


def _is_bip69_out(tx):
    pairs = [(o.get("value", 0), o.get("scriptpubkey", o.get("scriptpubkey_address", ""))) for o in tx["vout"]]
    amounts = [p[0] for p in pairs]
    if len(set(amounts)) != len(amounts):
        return pairs == sorted(pairs)
    return all(amounts[i] <= amounts[i + 1] for i in range(len(amounts) - 1))


def _low_r_scan(tx):
    """True if any input has a low-R ECDSA sig (DER r high-byte < 0x80); None if no witness."""
    any_data = False
    for v in tx["vin"]:
        for h in v.get("witness") or []:
            any_data = True
            if len(h) >= 18 and h[:2] == "30":
                b = bytes.fromhex(h)
                if len(b) >= 5 and b[2] == 0x02 and b[3] >= 1 and b[4] < 0x80:
                    return True
    return False if any_data else None


def _uncompressed_pubkey(tx):
    any_data = False
    for v in tx["vin"]:
        for h in v.get("witness") or []:
            any_data = True
            if len(h) == 130 and h[:2] == "04":
                return True
    return False if any_data else None


def _taproot_explicit_sighash(tx):
    any_data = False
    for v in tx["vin"]:
        if v.get("prevout", {}).get("scriptpubkey_type") not in ("v1_p2tr", "witness_v1_taproot"):
            continue
        wit = v.get("witness") or []
        if len(wit) == 1:
            any_data = True
            if len(wit[0]) == 130:   # 65 bytes -> explicit sighash byte
                return True
    return False if any_data else None


def _b(x):
    return None if x is None else int(x)


def vector(tx):
    """The 18-position vector. Witness axes are None when unavailable (caller skips them)."""
    seqs = _seqs(tx)
    lt = tx.get("locktime", 0)
    prevout_types = [v.get("prevout", {}).get("scriptpubkey_type") for v in tx["vin"]]
    in_addr = {v.get("prevout", {}).get("scriptpubkey_address") for v in tx["vin"]}
    out_addr = {o.get("scriptpubkey_address") for o in tx["vout"]}
    n_out = len(tx["vout"])
    return [
        int(any(s < 0xFFFFFFFE for s in seqs)),                       # 0 signals_rbf
        _b(_low_r_scan(tx)),                                          # 1 low_r_grinding (witness)
        int(lt != 0),                                                 # 2 anti_fee_snipe
        int(lt == 0 and any(s < 0xFFFFFFFE for s in seqs)),           # 3 nlocktime_optin_without_use
        int(lt > 0 and any(s < 0x80000000 for s in seqs)),            # 4 bip68_with_absolute_locktime
        _bitset(_otype(o.get("scriptpubkey_type")) for o in tx["vout"]),  # 5 output_types bitset
        0 if n_out == 1 else (1 if n_out == 2 else 2),                # 6 output_structure
        int(_is_bip69_out(tx)),                                       # 7 is_bip69_sorted outputs
        _bitset(_otype(t) for t in prevout_types),                    # 8 input_types bitset
        int(len({t for t in prevout_types if t is not None}) > 1),    # 9 mixed_input_types
        int(bool((in_addr & out_addr) - {None})),                     # 10 address_reuse
        _input_order(tx),                                             # 11 input_order bitset
        _b(_uncompressed_pubkey(tx)),                                 # 12 has_uncompressed_pubkey
        _b(_taproot_explicit_sighash(tx)),                            # 13 taproot explicit sighash
        _NSEQ.get(x_nsequence(tx), 5),                                # 14 nsequence_class
        _uih1(tx),                                                    # 15 uih1
        (_SIGHASH.get(x_sighash(tx), 8)                               # 16 sighash_class (witness)
         if any(v.get("witness") for v in tx["vin"]) else None),
        int(tx.get("version") or 0) & 0xFFFFFFFF,                     # 17 version
    ]


AXIS_NAMES = [
    "signals_rbf", "low_r_grinding", "anti_fee_snipe", "nlocktime_optin_without_use",
    "bip68_with_absolute_locktime", "output_types", "output_structure", "is_bip69_sorted",
    "input_types", "mixed_input_types", "address_reuse", "input_order",
    "has_uncompressed_pubkey", "taproot_explicit_sighash", "nsequence_class", "uih1",
    "sighash_class", "version",
]


# --- calibrate: measure bits -> rust_bits.json ---
def calibrate(sample):
    width = len(AXIS_NAMES)
    counts = [Counter() for _ in range(width)]
    totals = [0] * width
    for tx, _h in sample:
        try:
            vec = vector(tx)
        except Exception:
            continue
        for pos, val in enumerate(vec):
            if val is None: continue   # witness axis with no data on this tx
            counts[pos][val] += 1
            totals[pos] += 1
    table = [{str(v): -math.log2(k / totals[pos]) for v, k in counts[pos].items()} if totals[pos] else {}
             for pos in range(width)]
    return table, totals


def load_blkcache(path=".blkcache"):
    """Locally-cached mempool block-tx pages (witness-bearing) — fills witness axes BigQuery lacks."""
    seen, out = set(), []
    for f in glob.glob(f"{path}/*.json"):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for tx in (d if isinstance(d, list) else [d]):
            if not isinstance(tx, dict) or not tx.get("vin"): continue
            tid = tx.get("txid")
            if tid in seen: continue
            seen.add(tid); out.append((tx, tx.get("status", {}).get("block_height")))
    return out


def merge_witness(table, totals, wit):
    """Overwrite witness-dependent axes (empty from BigQuery) with mempool-measured bits."""
    wtable, wtotals = calibrate(wit)
    for pos in range(len(table)):
        if totals[pos] == 0 and wtotals[pos] > 0:
            table[pos], totals[pos] = wtable[pos], wtotals[pos]
    return len(wit)


# --- validate: does the model separate same-wallet from random pairs? ---
def load_model(path="rust_bits.json", consistency=0.95):
    raw = json.load(open(path))
    freq, collision, total = [], [], []
    for table in raw:
        f = {int(v): 2 ** -b for v, b in table.items()}
        freq.append(f)
        collision.append(sum(p * p for p in f.values()))
        total.append(1.0 / min(f.values()) if f else 1.0)
    return freq, collision, total, consistency


def score(a, b, model):
    """Fellegi-Sunter bits, replicating the Rust EvidenceModel::score exactly."""
    freq, collision, total, c = model
    bits = 0.0
    for pos in range(min(len(a), len(b), len(freq))):
        if a[pos] is None or b[pos] is None or collision[pos] >= 1.0: continue
        if a[pos] == b[pos]:
            p = freq[pos].get(a[pos], 1.0 / (total[pos] + 1.0))
            bits += -math.log2(p)
        else:
            bits += math.log2((1.0 - c) / max(1.0 - collision[pos], 1e-300))
    return bits


def evaluate(sample, model, seed=0, cap=4000):
    rng = random.Random(seed)
    vecs, addr_txs = [], {}
    for tx, _h in sample:
        try:
            v = vector(tx)
        except Exception:
            continue
        idx = len(vecs); vecs.append(v)
        for vin in tx.get("vin", []):
            a = (vin.get("prevout") or {}).get("scriptpubkey_address")
            if a: addr_txs.setdefault(a, set()).add(idx)
    pos_pairs = set()
    for txset in addr_txs.values():   # same-wallet = txs sharing an input address
        t = sorted(txset)
        for i in range(len(t)):
            for j in range(i + 1, len(t)):
                pos_pairs.add((t[i], t[j]))
    pos_pairs = list(pos_pairs)
    if len(pos_pairs) > cap:
        pos_pairs = rng.sample(pos_pairs, cap)
    pos = [score(vecs[i], vecs[j], model) for i, j in pos_pairs]
    n = len(vecs)
    neg = [score(vecs[rng.randrange(n)], vecs[rng.randrange(n)], model) for _ in range(cap)]
    ctrl = [score(vecs[rng.randrange(n)], vecs[rng.randrange(n)], model) for _ in range(len(pos))]
    return {"txs": n, "pos_pairs": len(pos), "auc": auc(pos, neg, seed),
            "auc_shuffle": auc(ctrl, neg, seed),
            "pos_mean": sum(pos) / len(pos) if pos else None,
            "neg_mean": sum(neg) / len(neg) if neg else None}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if cmd == "calibrate":
        args = [a for a in sys.argv[2:] if a != "--witness"]
        seen, sample = set(), []
        for p in args:
            for tx, h in load_ndjson(p):
                if tx.get("txid") in seen: continue
                seen.add(tx.get("txid")); sample.append((tx, h))
        table, totals = calibrate(sample)
        if "--witness" in sys.argv:
            print(f"# +{merge_witness(table, totals, load_blkcache())} cached mempool txs for witness axes")
        json.dump(table, open("rust_bits.json", "w"), indent=1)
        print(f"# calibrated on {len(sample)} txs -> rust_bits.json")
        for pos, name in enumerate(AXIS_NAMES):
            vals = table[pos]
            top = max(vals.items(), key=lambda kv: kv[1]) if vals else ("-", 0)
            print(f"  [{pos:2}] {name:30} n={totals[pos]:>6}  values={len(vals):>2}  rarest={top[0]}@{top[1]:.1f}b"
                  if vals else f"  [{pos:2}] {name:30} (no data)")
    else:
        path = sys.argv[2] if len(sys.argv) > 2 else ".blkcache"
        r = evaluate(load_blkcache(path), load_model())
        print(f"# {r['txs']} real witness-bearing txs; {r['pos_pairs']} same-wallet pairs (address reuse)")
        print(f"fingerprint score  same-wallet mean={r['pos_mean']:.2f}b  random mean={r['neg_mean']:.2f}b")
        print(f"AUC (fingerprint separates same-wallet from random): {r['auc']:.4f}")
        print(f"AUC shuffle control (expected ~0.5): {r['auc_shuffle']:.4f}")

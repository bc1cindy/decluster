"""Layer 1 — pure extractors: tx -> categorical fingerprint value."""
def locktime_policy(tx): return "zero" if tx.get("locktime", 0) == 0 else "height"

def seqs(tx): return [v["sequence"] for v in tx["vin"]]

def x_nsequence(tx):
    s = seqs(tx)
    if len(s) >= 2 and s[0] == 0x01 and all(v == 0xFFFFFFFF for v in s[1:]):
        return "cake_group_c"          # [0x01, MAX, ...]: Cake-specific signature
    if any(v == 0x01 for v in s):
        return "seq_0x01_other"        # lone 0x01: ambiguous (~2.5% on mainnet)
    if all(v == 0xFFFFFFFD for v in s): return "rbf_fffffffd"
    if all(v == 0xFFFFFFFE for v in s): return "final_fffffffe"
    if all(v == 0xFFFFFFFF for v in s): return "max_ffffffff"
    return "mixed_other"

def x_input_order(tx):
    o = [(v["txid"], v["vout"]) for v in tx["vin"]]
    n = len(o)
    if n == 1: return "single"
    if o != sorted(o): return "shuffle"                # not sorted -> not BIP-69 (reliable at any n)
    return "bip69" if n >= 4 else "small_n"            # sorted: brands BIP-69 only when accidental sort (1/n!) is small; n<=3 is coincidental (1/2, 1/6)

def x_io_shape(tx): return f"{len(tx['vin'])}in-{len(tx['vout'])}out"

def x_version(tx): return f"v{tx.get('version')}"

def x_output_order(tx):
    vals = [o["value"] for o in tx["vout"]]
    n = len(vals)
    if n == 1: return "single"
    if vals != sorted(vals): return "unsorted"          # not sorted -> reliable at any n
    return "sorted_value" if n >= 4 else "small_n"       # sorted: only brands at n>=4; n<=3 is coincidental (1/n!)

def x_change_spk_type(tx):
    types = {o["scriptpubkey_type"] for o in tx["vout"]}
    return f"uniform_{next(iter(types))}" if len(types) == 1 else "mixed"

def x_uih(tx):
    # UIH1: some single input alone exceeds the largest output -> an input was unnecessary
    in_vals = [iv for v in tx["vin"]
               if (iv := (v.get("prevout") or {}).get("value", v.get("value"))) is not None]
    out_vals = [o["value"] for o in tx["vout"]]
    if len(in_vals) < 2 or not out_vals: return "none"
    return "uih1" if max(in_vals) >= max(out_vals) else "none"

def features(tx):
    return {"shape": x_io_shape(tx), "nseq": x_nsequence(tx), "in_order": x_input_order(tx),
            "seqs": [hex(v) for v in seqs(tx)]}

def _witness_sig(vin):
    w = vin.get("witness") or []
    return w[0] if w else None

_SH = {"01": "all", "02": "none", "03": "single",
       "81": "anyonecanpay_all", "82": "anyonecanpay_none", "83": "anyonecanpay_single"}

def x_low_r(tx):
    lens = []
    for v in tx["vin"]:
        s = _witness_sig(v)
        if not s: continue
        n = len(s) // 2
        if 68 <= n <= 73: lens.append(n)   # ECDSA DER incl. sighash byte
    if not lens: return "na"
    return "low_r" if all(n <= 71 for n in lens) else "not_low_r"

def x_sighash(tx):
    cls = set()
    for v in tx["vin"]:
        s = _witness_sig(v)
        if not s: continue
        n = len(s) // 2
        if n == 64: cls.add("taproot_default")
        elif n == 65: cls.add("taproot_explicit")
        elif 68 <= n <= 73: cls.add(_SH.get(s[-2:].lower(), "sh_" + s[-2:].lower()))
    if not cls: return "na"
    return next(iter(cls)) if len(cls) == 1 else "mixed"

def x_fee_rate(tx):
    fee, w = tx.get("fee"), tx.get("weight")
    if not fee or not w: return "na"
    r = fee / (w / 4)                         # sat/vB
    nearest = round(r)
    if nearest >= 1 and abs(r - nearest) < 0.01:
        return "round"                        # manual-input integer fee rate
    return "precise"                          # estimator fractional

def x_input_script_type(tx):
    types = {(v.get("prevout") or {}).get("scriptpubkey_type") for v in tx["vin"]}
    types.discard(None)
    if not types: return "na"
    return f"uniform_{next(iter(types))}" if len(types) == 1 else "mixed"

def x_op_return(tx):
    return "has_op_return" if any(o.get("scriptpubkey_type") == "op_return" for o in tx["vout"]) else "none"

_ENC = {"p2pkh": "base58", "p2sh": "base58", "v0_p2wpkh": "bech32",
        "v0_p2wsh": "bech32", "v1_p2tr": "bech32m"}

def x_output_encoding(tx):
    encs = {_ENC.get(o.get("scriptpubkey_type")) for o in tx["vout"]
            if o.get("scriptpubkey_type") != "op_return"}
    encs.discard(None)
    if not encs: return "na"
    return next(iter(encs)) if len(encs) == 1 else "mixed"

def x_input_types_present(tx):
    types = sorted({(v.get("prevout") or {}).get("scriptpubkey_type") for v in tx["vin"]} - {None})
    return "+".join(types) if types else "na"

def x_nested_segwit(tx):
    # a P2SH input carrying a witness is nested segwit (P2SH-P2WPKH / P2SH-P2WSH)
    nested = any((v.get("prevout") or {}).get("scriptpubkey_type") == "p2sh" and v.get("witness")
                 for v in tx["vin"])
    return "nested_segwit" if nested else "none"

def x_pubkey_compression(tx):
    # p2wpkh inputs: last witness item is the pubkey; 33B/0x02-03 = compressed, 65B/0x04 = uncompressed
    kinds = set()
    for v in tx["vin"]:
        if (v.get("prevout") or {}).get("scriptpubkey_type") != "v0_p2wpkh": continue
        w = v.get("witness") or []
        if len(w) < 2: continue
        pk = w[-1]; n = len(pk) // 2
        if n == 33 and pk[:2].lower() in ("02", "03"): kinds.add("compressed")
        elif n == 65 and pk[:2].lower() == "04": kinds.add("uncompressed")
    if not kinds: return "na"
    return next(iter(kinds)) if len(kinds) == 1 else "mixed"

def x_multisig(tx):
    # basic: a redeemScript/witnessScript ending in OP_CHECKMULTISIG (0xae).
    # P2WSH -> last witness item; P2SH (legacy) -> last push of the scriptSig.
    for v in tx["vin"]:
        t = (v.get("prevout") or {}).get("scriptpubkey_type")
        if t == "v0_p2wsh":
            w = v.get("witness") or []
            if w and w[-1].lower().endswith("ae"): return "multisig"
        elif t == "p2sh":
            ss = (v.get("scriptsig") or "").lower()
            if ss.endswith("ae"): return "multisig"
    return "none"

from .subtransaction import roundness as _roundness

def _change_index(tx):
    # neutral change-id (2-out): change = the LESS-round output (payment is rounder).
    # round-number heuristic only -> independent of script type (avoids circularity).
    outs = tx.get("vout", [])
    if len(outs) != 2: return None
    r0, r1 = _roundness(outs[0]["value"]), _roundness(outs[1]["value"])
    if r0 == r1: return None            # ambiguous
    return 0 if r0 < r1 else 1          # less-round index = change

def x_change_index(tx):
    ci = _change_index(tx)
    if ci is None: return "na"
    return "first" if ci == 0 else "last"   # 2-out: change is idx 0 or 1

def x_change_type_match(tx):
    ci = _change_index(tx)
    if ci is None: return "na"
    ct = tx["vout"][ci].get("scriptpubkey_type")
    itypes = {(v.get("prevout") or {}).get("scriptpubkey_type") for v in tx["vin"]}
    return "match_input" if ct in itypes else "mismatch_input"

def x_change_matches_output(tx):
    ci = _change_index(tx)
    if ci is None: return "na"
    ot = tx["vout"][1 - ci].get("scriptpubkey_type")
    ct = tx["vout"][ci].get("scriptpubkey_type")
    return "match_output" if ct == ot else "mismatch_output"

def x_change_address_reuse(tx):
    ia = {(v.get("prevout") or {}).get("scriptpubkey_address") for v in tx["vin"]}
    ia.discard(None)
    oa = {o.get("scriptpubkey_address") for o in tx["vout"]}
    oa.discard(None)
    return "reuse" if ia & oa else "none"

from .broadcast import tx_feerate, broadcast_window, locktime_vs_broadcast

def x_locktime_vs_broadcast(tx):
    """nLocktime vs estimated broadcast height. Reads the tx['_bc'] annotation
    (prev_min/prev_time/incl_time); returns 'na' when unannotated / coinbase."""
    bc = tx.get("_bc")
    st = tx.get("status") or {}
    n = st.get("block_height")
    if bc is None or n is None:
        return "na"
    win = broadcast_window(tx_feerate(tx), bc["prev_min"], bc["prev_time"], bc["incl_time"])
    return locktime_vs_broadcast(tx.get("locktime", 0), n, win)

"""Entity-label detectors: named-entity attribution from on-chain structure alone — an INDEPENDENT
label source, disjoint from the co-spend heuristic, and so a seed set for the strong Narayanan-Shmatikov
claim (paper §8/§9) that co-spend labels cannot supply. These are self-contained recognizers (no
external address list, fully reproducible); curated super-cluster lists (SatoshiDice, Mt. Gox, exchanges)
are a separate, weaker-constraint layer (catalog/known-entities.md). Each detector emits
`(entity, kind, confidence, source)` tuples keyed by the address or edge they identify."""

# --- OP_RETURN payload length (BIP-47 notification carries an 80-byte blinded payment code) ---

def op_return_payload_len(spk):
    """Length in bytes of the data pushed by an OP_RETURN scriptPubKey (hex), or None if `spk` is not a
    single-push OP_RETURN. Handles direct pushes (0x01..0x4b) and OP_PUSHDATA1/2 (0x4c/0x4d)."""
    if not spk:
        return None
    try:
        b = bytes.fromhex(spk)
    except ValueError:
        return None
    if len(b) < 2 or b[0] != 0x6A:                      # OP_RETURN
        return None
    op = b[1]
    if 0x01 <= op <= 0x4B:
        n, hdr = op, 2
    elif op == 0x4C and len(b) >= 3:                    # OP_PUSHDATA1
        n, hdr = b[2], 3
    elif op == 0x4D and len(b) >= 4:                    # OP_PUSHDATA2 (little-endian)
        n, hdr = b[2] | (b[3] << 8), 4
    else:
        return None
    return n if len(b) == hdr + n else None             # exactly one push, no trailing data


def detect_bip47_notification(tx):
    """BIP-47 (PayNym) notification transaction: establishes a payment channel by paying the recipient's
    static notification address and carrying the sender's blinded payment code in an 80-byte OP_RETURN.
    The 80-byte push is the structural tell; returns a social-graph seed edge or None.

    The edge is (sender, recipient-notification-address): the sender is the input cluster (its first
    input reveals the pubkey used to blind the code), the recipient is the non-OP_RETURN, non-change
    output paid the notification. We surface the notification output's address as the recipient key;
    the caller clusters the inputs as the sender."""
    nots = [i for i, o in enumerate(tx.get("vout", [])) if op_return_payload_len(o.get("scriptpubkey")) == 80]
    if len(nots) != 1:
        return None
    pays = [o for i, o in enumerate(tx["vout"])
            if i not in nots and o.get("scriptpubkey_type") != "op_return"]
    if not pays:                                        # a notification tx must pay the notification address; OP_RETURN-only is some other 80-byte protocol
        return None
    notif_addr = pays[0].get("scriptpubkey_address")
    return {"entity": "bip47_notification", "kind": "protocol", "confidence": 0.9, "source": "detector",
            "recipient_notification_addr": notif_addr,
            "sender_inputs": [v.get("txid") for v in tx.get("vin", [])]}


# --- BitMEX: 3BMEX (base58 P2SH) / bc1qmex (bech32) vanity deposit addresses, 3-of-4 P2SH multisig ---

# Each prefix mapped to the space it leaves free, which is what decides whether a
# match is a label or a coincidence. "3BMEX" fixes four base58 characters past the
# P2SH version's '3'; "bc1qmex" fixes only three bech32 characters past the hrp and
# witness version, and 32**3 is small enough that a transaction with hundreds of
# addresses is expected to contain one by chance.
_BITMEX_PREFIXES = {"3BMEX": 58 ** 4, "bc1qmex": 32 ** 3}


def _is_bitmex_addr(addr):
    return _bitmex_space(addr) is not None


def _bitmex_space(addr):
    """How many addresses share the matched prefix by chance, or None if none matches."""
    if not addr:
        return None
    for prefix, space in _BITMEX_PREFIXES.items():
        if addr.startswith(prefix):
            return space
    return None


def detect_bitmex(tx):
    """BitMEX deposit addresses carry a `3BMEX…`/`bc1qmex…` vanity prefix (3-of-4 P2SH multisig in the
    legacy era; reissued to native bech32 in Oct 2023). Returns per-address entity labels for any output
    paying such an address (a deposit) or any input spending one (BitMEX moving funds).

    A vanity prefix is worth exactly its improbability, and that is a property of the transaction it is
    found in as much as of the prefix. Each hit carries `expected_collisions` — how many addresses of
    this transaction would carry the prefix by chance — and a `confidence` discounted by it. In a
    two-output payment the bech32 prefix is worth as much as the base58 one; in a coinjoin with hundreds
    of outputs it is worth almost nothing, and a flat 0.98 there labels a mix's change as an exchange.

    Within one transaction the discount stays small — a 382-output round expects 0.014 coincidences — so
    this discloses the rate rather than refusing the hit. It is the corpus that turns the rate into
    coincidences: 312 rounds of that size expect about four, and a caller scanning a corpus has to
    multiply. No structural test separates them here, because deciding whether a bech32 BitMEX deposit
    is P2WPKH or P2WSH would settle it by assumption rather than by evidence."""
    addresses = [o.get("scriptpubkey_address") for o in tx.get("vout", [])]
    addresses += [(v.get("prevout") or {}).get("scriptpubkey_address") for v in tx.get("vin", [])]
    scanned = sum(1 for a in addresses if a)

    def label(role, index, addr, space):
        expected = scanned / space
        return {"role": role, "index": index, "address": addr, "entity": "bitmex",
                "kind": "service", "confidence": round(0.98 / (1 + expected), 4),
                "expected_collisions": expected, "source": "detector"}

    hits = []
    for i, o in enumerate(tx.get("vout", [])):
        space = _bitmex_space(o.get("scriptpubkey_address"))
        if space:
            hits.append(label("output", i, o["scriptpubkey_address"], space))
    for i, v in enumerate(tx.get("vin", [])):
        addr = (v.get("prevout") or {}).get("scriptpubkey_address")
        space = _bitmex_space(addr)
        if space:
            hits.append(label("input", i, addr, space))
    return hits


# --- Dust fan-out ("Moby Dick" campaign): many tiny outputs sprayed at once ---

DUST_LIMIT = 1000       # sats; a large fan-out of outputs at/below this is a dust spray


def detect_dust_fanout(tx, min_outputs=20, dust_limit=DUST_LIMIT, min_dust_frac=0.9):
    """Dust fan-out — the "Moby Dick" pattern: a transaction spraying many dust-value outputs. Its
    primary use is a **guard**, not a same-owner label: a dusted address must NOT be clustered with the
    duster (dust ≠ ownership — the main confound for address-reuse clustering). Returns the dust outputs
    (address + value) when the tx matches, else []."""
    vout = tx.get("vout", [])
    if len(vout) < min_outputs:
        return []
    dust = [o for o in vout if isinstance(o.get("value"), int) and o["value"] <= dust_limit]
    if len(dust) < min_dust_frac * len(vout):
        return []
    return [{"role": "output", "address": o.get("scriptpubkey_address"), "value": o["value"],
             "entity": "dust_fanout", "kind": "pattern", "confidence": 0.6, "source": "detector"}
            for o in dust]


# --- SatoshiDice: `1dice…` vanity bet/payout addresses (2012–2013 gambling service) ---

_SATOSHIDICE_PREFIX = "1dice"


def detect_satoshidice(tx):
    """SatoshiDice used `1dice…` vanity addresses for its bet/house outputs. Unlike a custodial exchange
    hub, a gambling service has **recurring counterparties** — the same bettors return and play across
    several house addresses — so its addresses share payment-graph neighbours, the structure the strong
    Narayanan-Shmatikov claim needs. Returns per-address entity labels for outputs/inputs on a `1dice`
    address."""
    hits = []
    for i, o in enumerate(tx.get("vout", [])):
        a = o.get("scriptpubkey_address")
        if a and a.startswith(_SATOSHIDICE_PREFIX):
            hits.append({"role": "output", "index": i, "address": a,
                         "entity": "satoshidice", "kind": "service", "confidence": 0.97, "source": "detector"})
    for i, v in enumerate(tx.get("vin", [])):
        a = (v.get("prevout") or {}).get("scriptpubkey_address")
        if a and a.startswith(_SATOSHIDICE_PREFIX):
            hits.append({"role": "input", "index": i, "address": a,
                         "entity": "satoshidice", "kind": "service", "confidence": 0.97, "source": "detector"})
    return hits


# --- Mining pools: the coinbase scriptSig tag (a public protocol marker, not an address list) ---

# tag substring -> pool name. Tags are public coinbase markers; this is a reference table, not
# third-party address data. Matched case-insensitively against the coinbase input's decoded script.
_POOL_TAGS = {
    "antpool": "antpool", "f2pool": "f2pool", "viabtc": "viabtc", "slush": "slushpool",
    "braiins": "slushpool", "btc.com": "btccom", "poolin": "poolin", "1thash": "1thash",
    "58coin": "58coin", "huobi": "huobipool", "okpool": "okpool", "okex": "okexpool",
    "binance": "binancepool", "foundry": "foundryusa", "/mara": "marapool", "spiderpool": "spiderpool",
    "emcd": "emcd", "luxor": "luxor", "sbicrypto": "sbicrypto", "ultimuspool": "ultimuspool",
    "secpool": "secpool", "rawpool": "rawpool", "bytepool": "bytepool", "whitepool": "whitepool",
}


def _coinbase_script(tx):
    vin = tx.get("vin", [])
    if not vin or not vin[0].get("is_coinbase"):
        return None
    v = vin[0]
    return v.get("script_hex") or v.get("scriptsig") or v.get("coinbase")


def detect_mining_pool(tx):
    """Mining pool attribution from the **coinbase tag** — the ASCII marker pools embed in the coinbase
    input's scriptSig (`/F2Pool/`, `/AntPool/`, …), a public self-identification, not inferred KYC.
    Returns the pool name and its payout address (the largest-value output) when a known tag is present,
    else None. Only fires on coinbase transactions."""
    script = _coinbase_script(tx)
    if not script:
        return None
    try:
        text = bytes.fromhex(script).decode("ascii", "replace").lower()
    except ValueError:
        text = script.lower()
    pool = next((name for tag, name in _POOL_TAGS.items() if tag in text), None)
    if not pool:
        return None
    outs = [o for o in tx.get("vout", []) if o.get("scriptpubkey_address") and isinstance(o.get("value"), int)]
    payout = max(outs, key=lambda o: o["value"])["scriptpubkey_address"] if outs else None
    return {"entity": pool, "kind": "pool", "confidence": 0.95, "source": "detector", "payout_addr": payout}


# --- Behavioural patterns (proxies, NOT brand attributions): consolidation and batching ---

def detect_consolidation(tx, min_inputs=10, max_outputs=2):
    """Uneconomic-consolidation pattern — many inputs swept into one/two outputs. The on-chain **proxy**
    for exchange / custodial hot-wallet sweeps (the "Coinbase wallet" catalog row's `io_shape` tell). It
    flags the *behaviour*, not the brand: attributing a consolidation to a specific company still needs a
    curated seed. Returns a pattern label or None."""
    nin, nout = len(tx.get("vin", [])), len(tx.get("vout", []))
    if nin < min_inputs or nout > max_outputs:
        return None
    return {"entity": "consolidation", "kind": "pattern", "confidence": 0.5, "source": "detector",
            "n_inputs": nin, "n_outputs": nout}


def detect_batching(tx, min_outputs=10, dust_limit=DUST_LIMIT, max_dust_frac=0.5, min_fanout=4):
    """Batched-payout pattern — few inputs paying many *non-dust* outputs at once (distinct from a dust
    spray, which `detect_dust_fanout` handles). The on-chain **proxy** for an exchange's batched
    withdrawals; a behaviour flag, not a brand attribution. Returns a pattern label or None.

    `min_fanout` is what "few inputs" costs in code: a payout fans out, so its outputs outnumber its
    inputs several times over. Without it the remaining tests are met by every coinjoin — hundreds of
    non-dust outputs and no fan-out at all — and what the detector reports is the protocol rather than a
    service. A mix runs near 1.2 outputs per input and a batch runs to tens or hundreds, so the two are
    not close; the threshold sits between them and refuses rather than guesses in the gap."""
    vout = tx.get("vout", [])
    if len(vout) < min_outputs:
        return None
    if len(vout) < min_fanout * max(1, len(tx.get("vin", []))):
        return None
    dust = sum(1 for o in vout if isinstance(o.get("value"), int) and o["value"] <= dust_limit)
    if dust > max_dust_frac * len(vout):                 # mostly dust -> a spray, not a batch payout
        return None
    return {"entity": "batching", "kind": "pattern", "confidence": 0.5, "source": "detector",
            "n_outputs": len(vout)}


DETECTORS = {"bip47_notification": detect_bip47_notification, "bitmex": detect_bitmex,
             "dust_fanout": detect_dust_fanout, "satoshidice": detect_satoshidice,
             "mining_pool": detect_mining_pool, "consolidation": detect_consolidation,
             "batching": detect_batching}


# --- Curated entity lists: named super-clusters / services with no self-contained on-chain signature ---
# (SatoshiDice, Mt. Gox, exchanges, pools, Binance). These CANNOT be inferred from structure alone —
# an address is Mt. Gox only because a tagged dataset says so — so they come from an external NDJSON
# list, not a detector. The file is populated from curated sources (WalletExplorer/OXT/known tags); it
# is absent by default (no third-party address data is shipped in-repo).

import json as _json
import os as _os

CURATED_PATH = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                             "catalog", "entities.ndjson")


def load_curated(path=CURATED_PATH):
    """Address -> label dict from a curated NDJSON list. Each line:
    {"key": <address>, "entity": ..., "kind": ..., "source": ..., "confidence": ...}. Blank lines and
    `#` comments are skipped. Returns {} when the file is absent (the default — populate it externally)."""
    if not _os.path.exists(path):
        return {}
    out = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rec = _json.loads(line)
            if rec.get("key"):
                out[rec["key"]] = rec
    return out


def entity_of(addr, curated=None):
    """The entity label for an address: the curated list first (named super-clusters/services), then the
    self-contained address-keyed detector (BitMEX vanity). Returns a label dict or None. (BIP-47 and
    dust are tx-level patterns, not address attributions, so they are not resolved here.)"""
    if curated and addr in curated:
        return curated[addr]
    if _is_bitmex_addr(addr):
        return {"entity": "bitmex", "kind": "service", "confidence": 0.98, "source": "detector"}
    return None


def curated_labeler(curated):
    """Adapt a curated address->label map into a per-tx labeler (same shape as `detect_bitmex`) so it can
    feed `graph_deanon.entity_label_uf` as an independent same-owner label source."""
    def label(tx):
        hits = []
        for o in tx.get("vout", []):
            a = o.get("scriptpubkey_address")
            if a in curated:
                hits.append({"address": a, **curated[a]})
        for v in tx.get("vin", []):
            a = (v.get("prevout") or {}).get("scriptpubkey_address")
            if a in curated:
                hits.append({"address": a, **curated[a]})
        return hits
    return label


def entity_hub_addresses(sample, curated=None):
    """The set of known super-cluster / service addresses to pass as `cluster_refined(hubs=...)`: every
    address a named detector (BitMEX, SatoshiDice, mining-pool payout) or the curated list attributes to
    a service/super-cluster entity. Passed to the engine's topology guard, these can never act as a
    *distinctive* shared counterparty — a boundary condition, refuse-only. `sample`: iterable of txs."""
    hubs = set()
    for tx in sample:
        for det in (detect_bitmex, detect_satoshidice):
            for h in det(tx):
                if h.get("address"):
                    hubs.add(h["address"])
        r = detect_mining_pool(tx)
        if r and r.get("payout_addr"):
            hubs.add(r["payout_addr"])
    if curated:
        hubs |= {a for a, rec in curated.items() if rec.get("kind") in ("supercluster", "service")}
    return hubs


def entity_labels(tx):
    """Run every detector; return {name: result} for those that fired (non-empty)."""
    out = {}
    for name, fn in DETECTORS.items():
        r = fn(tx)
        if r:
            out[name] = r
    return out

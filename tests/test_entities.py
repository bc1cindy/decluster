"""Entity-label detectors emit INDEPENDENT (non-co-spend) seeds: BIP-47 notification txs (80-byte
OP_RETURN payment code) and BitMEX vanity/multisig deposit addresses. Both must fire on the real
signature and abstain on look-alikes (Runes/Omni OP_RETURNs, ordinary addresses)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import json, tempfile
from decluster.entities import (op_return_payload_len, detect_bip47_notification,
                                detect_bitmex, detect_dust_fanout, detect_satoshidice,
                                detect_mining_pool, detect_consolidation, detect_batching, entity_labels,
                                load_curated, entity_of, curated_labeler)

def _opret(payload_bytes):
    """OP_RETURN scriptPubKey (hex) pushing `payload_bytes` of zeros with the right pushdata opcode."""
    data = "00" * payload_bytes
    if payload_bytes <= 0x4B:
        return f"6a{payload_bytes:02x}{data}"
    if payload_bytes <= 0xFF:
        return f"6a4c{payload_bytes:02x}{data}"                       # OP_PUSHDATA1
    return f"6a4d{payload_bytes & 0xFF:02x}{(payload_bytes >> 8):02x}{data}"  # OP_PUSHDATA2 (LE)

# --- OP_RETURN payload length parser ---

def test_payload_len_direct_and_pushdata():
    assert op_return_payload_len(_opret(20)) == 20            # direct push
    assert op_return_payload_len(_opret(80)) == 80            # OP_PUSHDATA1 (BIP-47 size)
    assert op_return_payload_len(_opret(300)) == 300          # OP_PUSHDATA2
    assert op_return_payload_len("6a5d0714dfe5") is None      # Runes marker (6a5d = OP_RETURN OP_13), not a single push
    assert op_return_payload_len("76a914" + "00" * 20 + "88ac") is None  # P2PKH, not OP_RETURN
    assert op_return_payload_len(None) is None
    assert op_return_payload_len(f"6a1400{'00'*20}") is None  # trailing byte after the push -> reject

# --- BIP-47 notification tx ---

def _tx(vout, vin=None):
    return {"txid": "T", "vin": vin or [{"txid": "f0", "vout": 0}], "vout": vout}

def test_bip47_fires_on_80_byte_opreturn():
    tx = _tx([{"value": 10000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qnotif"},
              {"value": 0, "scriptpubkey_type": "op_return", "scriptpubkey": _opret(80)}])
    r = detect_bip47_notification(tx)
    assert r and r["entity"] == "bip47_notification"
    assert r["recipient_notification_addr"] == "bc1qnotif"
    assert r["sender_inputs"] == ["f0"]

def test_bip47_abstains_on_wrong_payload_and_double():
    # 40-byte OP_RETURN (typical Omni/other) -> not BIP-47
    assert detect_bip47_notification(_tx([{"value": 0, "scriptpubkey_type": "op_return", "scriptpubkey": _opret(40)}])) is None
    # two 80-byte OP_RETURNs -> ambiguous, abstain
    two = _tx([{"value": 0, "scriptpubkey_type": "op_return", "scriptpubkey": _opret(80)},
               {"value": 0, "scriptpubkey_type": "op_return", "scriptpubkey": _opret(80)}])
    assert detect_bip47_notification(two) is None
    # ordinary payment, no OP_RETURN
    assert detect_bip47_notification(_tx([{"value": 10000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qx"}])) is None
    # 80-byte OP_RETURN but no payment output -> some other protocol, not a notification tx
    assert detect_bip47_notification(_tx([{"value": 0, "scriptpubkey_type": "op_return", "scriptpubkey": _opret(80)}])) is None

# --- BitMEX vanity deposit addresses ---

def test_bitmex_fires_on_vanity_output_and_input():
    tx = _tx([{"value": 500000, "scriptpubkey_type": "p2sh", "scriptpubkey_address": "3BMEXabcdef"},
              {"value": 10000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qchange"}])
    hits = detect_bitmex(tx)
    assert len(hits) == 1 and hits[0]["role"] == "output" and hits[0]["entity"] == "bitmex"
    # bech32-era deposit + BitMEX spending one of its own deposits (input)
    tx2 = _tx([{"value": 1, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qmexdeadbeef"}],
              vin=[{"txid": "f1", "vout": 0, "prevout": {"scriptpubkey_address": "3BMEXspend"}}])
    roles = {h["role"] for h in detect_bitmex(tx2)}
    assert roles == {"output", "input"}

def test_satoshidice_fires_on_1dice_prefix():
    tx = _tx([{"value": 20000, "scriptpubkey_type": "p2pkh", "scriptpubkey_address": "1dice8EMZmqKvrGE4Qc9bUFf9PX3xaYDp"},
              {"value": 5000, "scriptpubkey_type": "p2pkh", "scriptpubkey_address": "1bettorchange"}])
    hits = detect_satoshidice(tx)
    assert len(hits) == 1 and hits[0]["entity"] == "satoshidice" and hits[0]["role"] == "output"
    assert detect_satoshidice(_tx([{"value": 1, "scriptpubkey_type": "p2pkh", "scriptpubkey_address": "1ordinaryaddr"}])) == []

def test_bitmex_abstains_on_ordinary_addresses():
    assert detect_bitmex(_tx([{"value": 1, "scriptpubkey_type": "p2sh", "scriptpubkey_address": "3JZq0M…"},
                              {"value": 1, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qordinary"}])) == []

def _cb(script_ascii, outs):
    return {"vin": [{"is_coinbase": True, "script_hex": script_ascii.encode().hex()}],
            "vout": [{"value": v, "scriptpubkey_address": a} for v, a in outs]}

def test_mining_pool_reads_coinbase_tag():
    tx = _cb("\x03abcdef/F2Pool/mined", [(625000000, "1poolpayout"), (0, "1witnesscommit")])
    r = detect_mining_pool(tx)
    assert r and r["entity"] == "f2pool" and r["payout_addr"] == "1poolpayout"
    # unknown tag or non-coinbase -> None
    assert detect_mining_pool(_cb("\x03random nonce data", [(1, "1a")])) is None
    assert detect_mining_pool({"vin": [{"is_coinbase": False, "txid": "f", "vout": 0}], "vout": []}) is None

def test_consolidation_pattern():
    many_in = {"vin": [{"txid": f"f{i}", "vout": 0, "prevout": {"value": 1000}} for i in range(12)],
               "vout": [{"value": 11000, "scriptpubkey_address": "1hot"}]}
    assert detect_consolidation(many_in)["entity"] == "consolidation"
    # ordinary 2-in/2-out payment does not fire
    assert detect_consolidation({"vin": [{}, {}], "vout": [{"value": 1}, {"value": 2}]}) is None

def test_batching_pattern_not_dust():
    batch = {"vin": [{"txid": "f", "vout": 0}],
             "vout": [{"value": 500000, "scriptpubkey_address": f"1w{i}"} for i in range(15)]}
    assert detect_batching(batch)["entity"] == "batching"
    # a dust spray is NOT a batch payout (dust_fanout handles it)
    spray = {"vin": [{"txid": "f", "vout": 0}], "vout": [{"value": 546} for _ in range(15)]}
    assert detect_batching(spray) is None
    # a normal 2-output payment does not fire
    assert detect_batching({"vin": [{}], "vout": [{"value": 1}, {"value": 2}]}) is None

def test_entity_labels_dispatch():
    tx = _tx([{"value": 500000, "scriptpubkey_type": "p2sh", "scriptpubkey_address": "3BMEXaa"},
              {"value": 0, "scriptpubkey_type": "op_return", "scriptpubkey": _opret(80)}])
    got = entity_labels(tx)
    assert set(got) == {"bitmex", "bip47_notification"}

# --- Dust fan-out (Moby Dick) ---

def test_dust_fanout_fires_on_spray_not_on_normal():
    spray = _tx([{"value": 546, "scriptpubkey_type": "p2pkh", "scriptpubkey_address": f"1dust{i}"} for i in range(30)])
    hits = detect_dust_fanout(spray)
    assert len(hits) == 30 and hits[0]["entity"] == "dust_fanout"
    # a normal 2-output payment must not fire
    assert detect_dust_fanout(_tx([{"value": 500000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qa"},
                                   {"value": 12345, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": "bc1qb"}])) == []
    # many outputs but NOT dust (a batch payout) must not fire
    batch = _tx([{"value": 5_000_000, "scriptpubkey_type": "v0_p2wpkh", "scriptpubkey_address": f"bc1q{i}"} for i in range(30)])
    assert detect_dust_fanout(batch) == []

# --- Curated list loader ---

def test_curated_loader_and_entity_of():
    with tempfile.NamedTemporaryFile("w", suffix=".ndjson", delete=False) as f:
        f.write("# comment line, skip me\n")
        f.write(json.dumps({"key": "1GoxAddr", "entity": "mtgox", "kind": "supercluster", "source": "test", "confidence": 0.95}) + "\n")
        f.write("\n")                                    # blank line, skip
        f.write(json.dumps({"key": "1BinanceAddr", "entity": "binance", "kind": "service", "source": "test", "confidence": 0.9}) + "\n")
        path = f.name
    cur = load_curated(path)
    assert set(cur) == {"1GoxAddr", "1BinanceAddr"}
    assert entity_of("1GoxAddr", cur)["entity"] == "mtgox"        # curated wins
    assert entity_of("3BMEXaa")["entity"] == "bitmex"            # detector fallback (no curated needed)
    assert entity_of("1unknown", cur) is None
    assert load_curated("/no/such/path.ndjson") == {}            # absent file -> empty, not an error

def test_curated_labeler_feeds_entity_partition():
    cur = {"1GoxA": {"entity": "mtgox", "kind": "supercluster"}, "1GoxB": {"entity": "mtgox", "kind": "supercluster"}}
    lab = curated_labeler(cur)
    tx = {"vin": [{"txid": "f", "vout": 0, "prevout": {"scriptpubkey_address": "1GoxA"}}],
          "vout": [{"value": 1, "scriptpubkey_address": "1GoxB"}, {"value": 2, "scriptpubkey_address": "1other"}]}
    addrs = {h["address"] for h in lab(tx)}
    assert addrs == {"1GoxA", "1GoxB"}                           # both Gox addrs surfaced, the stranger ignored

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")

# --- Detectors that read a payment's shape must not read a coinjoin's ---
# Measured on six mainnet Wasabi 2 rounds and their funders: of 387 transactions
# scanned, 312 were mixes, `batching` fired on 312 of them, and `bitmex` fired
# twice — both times on a coinjoin output whose bech32 encoding happens to begin
# `bc1qmex`. Neither detector was wrong about payments. Both were being asked
# about a population where their signature carries no information.

def _mix(n_in=324, n_out=382, addr=None):
    """A coinjoin's shape: many non-dust outputs, and no fan-out at all."""
    vout = [{"value": 1_000_000, "scriptpubkey_address": f"bc1qout{i}"} for i in range(n_out)]
    if addr:
        vout[0]["scriptpubkey_address"] = addr
    return {"vin": [{"txid": f"f{i}", "vout": 0} for i in range(n_in)], "vout": vout}

def test_batching_refuses_a_coinjoin_however_many_outputs_it_pays():
    """A mix meets every other test — hundreds of outputs, almost no dust — and is
    separated only by the fan-out the description always claimed."""
    assert detect_batching(_mix()) is None
    assert detect_batching(_mix(n_in=454, n_out=502)) is None
    assert detect_batching(_mix(n_in=12, n_out=21)) is None      # a JoinMarket round

def test_batching_still_fires_on_a_payout_that_actually_fans_out():
    """The fix must not cost the pattern it exists for: one input, many payees."""
    assert detect_batching(_mix(n_in=1, n_out=101))["entity"] == "batching"
    assert detect_batching(_mix(n_in=3, n_out=12))["entity"] == "batching"

def test_the_fan_out_threshold_refuses_the_gap_rather_than_guessing():
    """A mix runs near 1.2 outputs per input, a payout to tens; between them the
    detector declines instead of picking a side."""
    assert detect_batching(_mix(n_in=5, n_out=15)) is None       # 3.0, under the bar
    assert detect_batching(_mix(n_in=5, n_out=20))["entity"] == "batching"

def test_a_bech32_prefix_match_is_discounted_by_how_many_addresses_were_scanned():
    """`bc1qmex` fixes three bech32 characters, so one address in 32768 carries it
    by chance. A two-output payment offers two chances and a coinjoin offers
    hundreds, and reporting both at a flat 0.98 is what let a mix's change be
    labelled an exchange.

    The discount within one transaction is real but small — a 382-output round
    still only expects 0.012 coincidences. It is the corpus that produces them:
    scanning 312 such rounds expects about 3.6, and 2 were found. Deciding that
    needs the scan size, which no detector sees, so what this reports is the
    per-transaction rate the caller has to multiply."""
    payment = _tx([{"value": 1, "scriptpubkey_type": "v0_p2wpkh",
                    "scriptpubkey_address": "bc1qmexdeadbeef"},
                   {"value": 1, "scriptpubkey_type": "v0_p2wpkh",
                    "scriptpubkey_address": "bc1qchange"}])
    strong = detect_bitmex(payment)[0]
    weak = detect_bitmex(_mix(addr="bc1qmexcollision"))[0]
    assert weak["confidence"] < strong["confidence"]
    assert weak["expected_collisions"] > 100 * strong["expected_collisions"]
    # monotone in the crowd: a bigger scan discounts the same prefix further
    # 32768 addresses is where a coincidence becomes the expectation, not the surprise
    bigger = detect_bitmex(_mix(n_in=1, n_out=65_536, addr="bc1qmexcollision"))[0]
    assert bigger["expected_collisions"] == 2 and bigger["confidence"] < 0.34

def test_the_base58_prefix_survives_the_same_transaction():
    """`3BMEX` fixes four base58 characters, a space three hundred times larger, so
    the same crowd does not erode it. The discount is per prefix, not per shape."""
    hit = detect_bitmex(_mix(addr="3BMEXcollision"))[0]
    weak = detect_bitmex(_mix(addr="bc1qmexcollision"))[0]
    assert hit["confidence"] > 0.97
    assert hit["expected_collisions"] < weak["expected_collisions"] / 100

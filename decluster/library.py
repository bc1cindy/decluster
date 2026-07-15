"""Layer 0 —  fingerprint library: axis -> extractor, measured bits, chain-proven
example (real txid).

Bit provenance:
- structural/amount/type/change: uniform ~105k whole-chain sample via BigQuery
  (`bigquery/`, `measure_file.py`), accumulated over several TABLESAMPLE runs.
- witness (low_r, sighash, pubkey_compression, multisig, nested_segwit) and op_return:
  ~3.5k mempool.space txs (`bigmeasure.py`) — BigQuery's schema has no witness."""

_EX3 = "8fb80573d8871efee060a34dcb97fd12d5229444b7262b26358cd84912a04a75"

AXES = [
    # --- structural / amount / type / change: BigQuery whole-chain (~105k txs) ---
    {"axis": "nsequence", "extractor": "x_nsequence", "severity": "high",
     "chain_proven": _EX3,
     "bits": {"max_ffffffff": 0.82, "rbf_fffffffd": 2.35, "final_fffffffe": 2.42,
              "mixed_other": 4.38, "seq_0x01_other": 8.89, "cake_group_c": 13.88}},
    {"axis": "locktime", "extractor": "locktime_class", "severity": "high",
     "chain_proven": _EX3,
     "bits": {"zero": 0.43, "height_backdated": 2.94, "height_tip": 3.01,
              "height_other": 7.65, "timestamp": 10.85}},   # zero~74-83%: TRUE chain dist
    {"axis": "input_order", "extractor": "x_input_order", "severity": "medium",
     "chain_proven": None,
     "bits": {"single": 0.53, "shuffle": 2.46, "bip69": 3.00}},
    {"axis": "output_order", "extractor": "x_output_order", "severity": "high",
     "chain_proven": None,
     "bits": {"sorted_value": 1.43, "unsorted": 1.61, "single": 1.72}},
    {"axis": "change_spk", "extractor": "x_change_spk_type", "severity": "medium",
     "chain_proven": None,
     "bits": {"uniform_p2pkh": 0.92, "mixed": 1.77, "uniform_v0_p2wpkh": 3.42,
              "uniform_p2sh": 3.96, "uniform_v1_p2tr": 5.92, "uniform_v0_p2wsh": 8.26}},
    {"axis": "version", "extractor": "x_version", "severity": "low",
     "chain_proven": None, "bits": {"v1": 0.67, "v2": 1.42, "v3": 11.60}},
    {"axis": "io_shape", "extractor": "x_io_shape", "severity": "low",
     "chain_proven": None, "bits": {"1in-2out": 1.38, "1in-1out": 2.17,
              "2in-2out": 3.95, "3in-2out": 4.31}},
    {"axis": "uih", "extractor": "x_uih", "severity": "medium",
     "chain_proven": None, "bits": {"none": 0.12, "uih1": 3.59}},   # medido (input values reais)
    {"axis": "fee_rate", "extractor": "x_fee_rate", "severity": "medium",
     "chain_proven": "16d3fad11242d95da3d12991e176b04cbb474bda95b968b3c4635453d4f9c90e",
     "bits": {"precise": 0.28, "round": 2.53, "na": 7.99}},
    {"axis": "input_script_type", "extractor": "x_input_script_type", "severity": "high",
     "chain_proven": "dce69633124d7a3240cc76de5fcc947881f6a140d6d2d0b009f70938136c6bb9",
     "bits": {"uniform_p2pkh": 0.87, "uniform_v0_p2wpkh": 2.18, "uniform_p2sh": 2.59,
              "uniform_v1_p2tr": 4.68, "mixed": 6.00, "uniform_v0_p2wsh": 6.71}},
    {"axis": "output_encoding", "extractor": "x_output_encoding", "severity": "medium",
     "chain_proven": "0361ae989850134b483cbf04b04978f331b0e6095dcf91de9737f4bde516367a",
     "bits": {"base58": 0.38, "bech32": 2.93, "mixed": 3.71, "bech32m": 5.50, "na": 9.15}},
    {"axis": "input_types_present", "extractor": "x_input_types_present", "severity": "high",
     "chain_proven": "dce69633124d7a3240cc76de5fcc947881f6a140d6d2d0b009f70938136c6bb9",
     "bits": {"p2pkh": 0.87, "v0_p2wpkh": 2.18, "p2sh": 2.59, "v1_p2tr": 4.68,
              "v0_p2wsh": 6.71, "p2pkh+p2sh": 7.58, "p2pkh+v0_p2wpkh": 8.20}},
    {"axis": "change_index", "extractor": "x_change_index", "severity": "medium",
     "chain_proven": "23b4362769380ec71fce09d0fbae5a1cd2b77baf375131b02e4c627f30226bca",
     "bits": {"na": 0.48, "last": 2.59, "first": 3.10}},
    {"axis": "change_type_match", "extractor": "x_change_type_match", "severity": "medium",
     "chain_proven": "2d498d460721523be79a32f0a27f27b3af0f91e4a6c69ace54d4a4304c6b53d8",
     "bits": {"na": 0.48, "match_input": 1.92, "mismatch_input": 5.72}},
    {"axis": "change_matches_output", "extractor": "x_change_matches_output", "severity": "low",
     "chain_proven": "fcc52ff920c440c0cc343485829faf422ff29215073f5de91947c9448577c671",
     "bits": {"na": 0.48, "match_output": 2.35, "mismatch_output": 3.52}},
    {"axis": "change_address_reuse", "extractor": "x_change_address_reuse", "severity": "high",
     "chain_proven": "8641cc137c82a9b01e6d2c985fb675bdcd23d170c99a13c23ce5cdac93976662",
     "bits": {"none": 0.37, "reuse": 2.14}},   # heuristic-free
    # --- witness / op_return: mempool.space sample (~3.5k; BigQuery has no witness) ---
    {"axis": "low_r", "extractor": "x_low_r", "severity": "low",
     "chain_proven": "dce69633124d7a3240cc76de5fcc947881f6a140d6d2d0b009f70938136c6bb9",
     "bits": {"na": 0.64, "low_r": 2.30, "not_low_r": 2.68}},
    {"axis": "sighash", "extractor": "x_sighash", "severity": "low",
     "chain_proven": "0361ae989850134b483cbf04b04978f331b0e6095dcf91de9737f4bde516367a",
     "bits": {"na": 0.81, "all": 1.49, "taproot_default": 3.96, "mixed": 7.38,
              "taproot_explicit": 8.31}},
    {"axis": "op_return", "extractor": "x_op_return", "severity": "medium",
     "chain_proven": "c5e61c145a0a5abd1c23c0ade88e8ef3ba01bd92beaa921ae662a4bd2ac11d55",
     "bits": {"none": 0.09, "has_op_return": 4.00}},
    {"axis": "nested_segwit", "extractor": "x_nested_segwit", "severity": "medium",
     "chain_proven": "dce69633124d7a3240cc76de5fcc947881f6a140d6d2d0b009f70938136c6bb9",
     "bits": {"none": 0.17, "nested_segwit": 3.15}},
    {"axis": "pubkey_compression", "extractor": "x_pubkey_compression", "severity": "low",
     "chain_proven": "b5240925e5acb0638de1ca8afca4a2e03fe475cd0cfe04986ad14e85740ec1b3",
     "bits": {"na": 0.46, "compressed": 1.86}},
    {"axis": "multisig", "extractor": "x_multisig", "severity": "medium",
     "chain_proven": "065ba81e754450f0f8ae373bf56b0bc3ef454b981f31db9ca92a7280f6ceb623",
     "bits": {"none": 0.09, "multisig": 4.02}},
    {"axis": "locktime_vs_broadcast", "extractor": "x_locktime_vs_broadcast", "severity": "medium",
     "chain_proven": "0ab4abca70d71f4554baa708a75604c0f05ad43f21f23cb0b25bd3e0e308b129",
     # na_loose = abstention (loose bound): non-evidential, weight 0. It is rare (~0.3%), but
     # rarity is not owner-linkage — "both waited during congestion" is a market-wide condition,
     # so scoring it by -log2(share) would forge a false same-owner link if fed to the combiner.
     "bits": {"no_locktime": 0.22, "matches": 2.85, "na_loose": 0.0, "backdated": 9.48}},
]

_BY = {a["axis"]: a for a in AXES}

def bits(axis, value):
    """Evidence bits for (axis, value); None if the axis is unmeasured or the value unknown."""
    a = _BY.get(axis)
    if not a or not a.get("bits"): return None
    return a["bits"].get(value)

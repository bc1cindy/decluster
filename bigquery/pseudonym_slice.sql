-- Contiguous two-epoch slice for cross-view pseudonym-graph matching, exported in the
-- JSON schema the Python extractors already consume (same trick as sample.sql), so the
-- pipeline runs on it unchanged.
--
-- Unlike graph.sql (addresses only, coinbase excluded) and slice.sql (lean, no coinbase),
-- this carries what the contraction and the matcher need: values for edge weights and the
-- amount channel, script types for type-segregated matching and vertex attributes, the
-- fingerprint fields cluster_refined's combiner reads, and the coinbase tag that seeds
-- the matching with self-identifying pool vertices.
--
-- MUST-KNOWs, each one measured rather than assumed:
--   * Partition pruning is on block_timestamp_month and is not optional. Filtering only on
--     block_number scans the whole table.
--   * Coinbase transactions carry NO inputs in this dataset (input_count = 0), so the
--     coinbase scriptSig is absent from `transactions`. It lives in `blocks.coinbase_param`,
--     hence the join. Without it detect_mining_pool has nothing to fire on.
--   * UNNEST does not preserve array order, and the input_order / output_order axes and
--     BIP-69 depend on it. Both arrays are explicitly ORDER BY index.
--   * Values are satoshis (verified against a coinbase output vs the 3.125 BTC subsidy).
--   * `weight` is derived as virtual_size * 4. vsize = ceil(weight/4), so this overshoots
--     by up to 3 weight units. Immaterial for feerate bucketing, wrong for exact weight.
--   * The public dataset is missing 835 blocks above height 959194 (largest gap
--     962010-962489). Keep the slice below that.
--   * Script types use a DIFFERENT vocabulary here than the extractors expect
--     (`witness_v0_keyhash` vs `v0_p2wpkh`), and there is no op_return type at all: an
--     OP_RETURN output is reported as `nonstandard` (15916 of 16024 nonstandard outputs in
--     a 10-block probe; the remaining 108 are bare multisig). Untranslated, every type and
--     encoding axis reads as unknown and the OP_RETURN axis never fires, silently. Hence
--     the CASE below, which derives op_return from the script prefix rather than the label.
--
-- Witness-dependent axes cannot be fed from here (documented in bigquery/README.md):
-- low_r, sighash and pubkey_compression correctly abstain as `na`, but multisig and
-- nested_segwit report `none` rather than abstaining, which is a FALSE negative, not a
-- missing value. Exclude those two when scoring on this export; the three axes
-- cluster_refined's combiner uses (nsequence, locktime, input order) are unaffected.
--
-- Two epochs of 144 blocks separated by seven epochs: the view separation
-- results/RESULTS-attribute-drift.md argues for, since drift dips at multiples of 7.
-- Edit the ranges and the partition month together; 1 epoch = 144 blocks ~= 1 day.
--
-- Export as NEWLINE-DELIMITED JSON, then run the pipeline on the result.

WITH blk AS (
  SELECT `number`, coinbase_param
  FROM `bigquery-public-data.crypto_bitcoin.blocks`
  WHERE `number` BETWEEN 939969 AND 941120
)
SELECT TO_JSON_STRING(STRUCT(
  t.hash AS txid,
  t.block_number AS height,
  t.version AS version,
  t.lock_time AS locktime,
  CAST(t.fee AS INT64) AS fee,
  t.virtual_size * 4 AS weight,
  IF(t.is_coinbase,
     [STRUCT(TRUE AS is_coinbase,
             b.coinbase_param AS script_hex,
             CAST(NULL AS STRING) AS txid,
             CAST(NULL AS INT64) AS vout,
             CAST(NULL AS INT64) AS sequence,
             STRUCT(CAST(NULL AS INT64) AS value,
                    CAST(NULL AS STRING) AS scriptpubkey_type,
                    CAST(NULL AS STRING) AS scriptpubkey_address) AS prevout)],
     ARRAY(SELECT AS STRUCT
             FALSE AS is_coinbase,
             CAST(NULL AS STRING) AS script_hex,
             i.spent_transaction_hash AS txid,
             i.spent_output_index AS vout,
             i.sequence AS sequence,
             STRUCT(CAST(i.value AS INT64) AS value,
                    CASE i.type
                      WHEN 'pubkeyhash' THEN 'p2pkh'
                      WHEN 'scripthash' THEN 'p2sh'
                      WHEN 'witness_v0_keyhash' THEN 'v0_p2wpkh'
                      WHEN 'witness_v0_scripthash' THEN 'v0_p2wsh'
                      WHEN 'witness_v1_taproot' THEN 'v1_p2tr'
                      ELSE i.type END AS scriptpubkey_type,
                    i.addresses[SAFE_OFFSET(0)] AS scriptpubkey_address) AS prevout
           FROM UNNEST(t.inputs) i ORDER BY i.index)) AS vin,
  ARRAY(SELECT AS STRUCT
          CAST(o.value AS INT64) AS value,
          CASE
            WHEN STARTS_WITH(o.script_hex, '6a') THEN 'op_return'
            WHEN o.type = 'pubkeyhash' THEN 'p2pkh'
            WHEN o.type = 'scripthash' THEN 'p2sh'
            WHEN o.type = 'witness_v0_keyhash' THEN 'v0_p2wpkh'
            WHEN o.type = 'witness_v0_scripthash' THEN 'v0_p2wsh'
            WHEN o.type = 'witness_v1_taproot' THEN 'v1_p2tr'
            ELSE o.type END AS scriptpubkey_type,
          o.addresses[SAFE_OFFSET(0)] AS scriptpubkey_address,
          o.script_hex AS scriptpubkey
        FROM UNNEST(t.outputs) o ORDER BY o.index) AS vout
)) AS row
FROM `bigquery-public-data.crypto_bitcoin.transactions` AS t
LEFT JOIN blk AS b ON b.number = t.block_number
WHERE t.block_timestamp_month = '2026-03-01'
  AND (t.block_number BETWEEN 939969 AND 940112
    OR t.block_number BETWEEN 940977 AND 941120)

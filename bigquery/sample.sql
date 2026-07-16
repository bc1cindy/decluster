-- Large unbiased mainnet sample -> the fingerprint pipeline's JSON schema.
-- Source: bigquery-public-data.crypto_bitcoin.transactions (whole chain, no node).
-- TABLESAMPLE reads only ~0.05% of the table's blocks -> free-tier friendly AND a
-- uniform random sample (~500k txs). Raise/lower the percent to change sample size.
--
-- Run in the BigQuery console (or `bq query --use_legacy_sql=false --format=csv ...`),
-- export the result as NEWLINE-DELIMITED JSON (one row = the `row` column), then:
--   python3 -m decluster.measure file sample.ndjson
--
-- The `type` values are normalized from BigQuery's names to mempool.space's so the
-- existing Python extractors run unchanged. Witness-dependent axes (low-R, sighash,
-- pubkey compression, multisig) will read "na" here — BigQuery has no witness data;
-- those stay measured on the mempool sample (documented in the paper).

SELECT TO_JSON_STRING(STRUCT(
  t.hash AS txid,
  t.block_number AS height,
  t.version AS version,
  t.lock_time AS locktime,
  t.fee AS fee,
  t.virtual_size * 4 AS weight,          -- so weight/4 = vsize (x_fee_rate)
  ARRAY(
    SELECT AS STRUCT
      i.spent_transaction_hash AS txid,
      i.spent_output_index      AS vout,
      i.sequence                AS sequence,
      i.value                   AS value,          -- top-level (x_uih)
      STRUCT(
        i.value AS value,
        CASE i.type
          WHEN 'pubkeyhash'            THEN 'p2pkh'
          WHEN 'scripthash'           THEN 'p2sh'
          WHEN 'witness_v0_keyhash'   THEN 'v0_p2wpkh'
          WHEN 'witness_v0_scripthash' THEN 'v0_p2wsh'
          WHEN 'witness_v1_taproot'   THEN 'v1_p2tr'
          WHEN 'pubkey'               THEN 'p2pk'
          WHEN 'multisig'             THEN 'multisig'
          WHEN 'nulldata'             THEN 'op_return'
          ELSE i.type
        END AS scriptpubkey_type,
        (SELECT a FROM UNNEST(i.addresses) a LIMIT 1) AS scriptpubkey_address
      ) AS prevout
    FROM UNNEST(t.inputs) i
  ) AS vin,
  ARRAY(
    SELECT AS STRUCT
      o.value AS value,
      CASE o.type
        WHEN 'pubkeyhash'            THEN 'p2pkh'
        WHEN 'scripthash'           THEN 'p2sh'
        WHEN 'witness_v0_keyhash'   THEN 'v0_p2wpkh'
        WHEN 'witness_v0_scripthash' THEN 'v0_p2wsh'
        WHEN 'witness_v1_taproot'   THEN 'v1_p2tr'
        WHEN 'pubkey'               THEN 'p2pk'
        WHEN 'multisig'             THEN 'multisig'
        WHEN 'nulldata'             THEN 'op_return'
        ELSE o.type
      END AS scriptpubkey_type,
      (SELECT a FROM UNNEST(o.addresses) a LIMIT 1) AS scriptpubkey_address
    FROM UNNEST(t.outputs) o
  ) AS vout
)) AS row
FROM `bigquery-public-data.crypto_bitcoin.transactions` AS t
     TABLESAMPLE SYSTEM (0.05 PERCENT)
WHERE t.is_coinbase = FALSE

SELECT
  t.hash AS txid, t.block_number AS height, t.version AS version,
  t.lock_time AS locktime, t.fee AS fee, t.virtual_size * 4 AS weight,
  ARRAY(SELECT AS STRUCT
    i.spent_transaction_hash AS txid, i.spent_output_index AS vout,
    i.sequence AS sequence, i.value AS value,
    STRUCT(i.value AS value,
      CASE i.type WHEN 'pubkeyhash' THEN 'p2pkh' WHEN 'scripthash' THEN 'p2sh'
        WHEN 'witness_v0_keyhash' THEN 'v0_p2wpkh' WHEN 'witness_v0_scripthash' THEN 'v0_p2wsh'
        WHEN 'witness_v1_taproot' THEN 'v1_p2tr' WHEN 'pubkey' THEN 'p2pk'
        WHEN 'nulldata' THEN 'op_return' ELSE i.type END AS scriptpubkey_type,
      (SELECT a FROM UNNEST(i.addresses) a LIMIT 1) AS scriptpubkey_address) AS prevout
    FROM UNNEST(t.inputs) i) AS vin,
  ARRAY(SELECT AS STRUCT
    o.value AS value,
    CASE o.type WHEN 'pubkeyhash' THEN 'p2pkh' WHEN 'scripthash' THEN 'p2sh'
      WHEN 'witness_v0_keyhash' THEN 'v0_p2wpkh' WHEN 'witness_v0_scripthash' THEN 'v0_p2wsh'
      WHEN 'witness_v1_taproot' THEN 'v1_p2tr' WHEN 'pubkey' THEN 'p2pk'
      WHEN 'nulldata' THEN 'op_return' ELSE o.type END AS scriptpubkey_type,
    (SELECT a FROM UNNEST(o.addresses) a LIMIT 1) AS scriptpubkey_address
    FROM UNNEST(t.outputs) o) AS vout
FROM `bigquery-public-data.crypto_bitcoin.transactions` AS t
TABLESAMPLE SYSTEM (0.005 PERCENT)
WHERE t.is_coinbase = FALSE
LIMIT 15000

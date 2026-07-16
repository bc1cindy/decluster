-- Contiguous time-window slice -> the fingerprint pipeline's JSON schema, WITH forward-spend links.
-- Unlike sample.sql (uniform TABLESAMPLE, for frequency calibration), this exports EVERY tx in a
-- window so (a) multi-input clusters and (b) each output's spending tx are IN-SAMPLE. That enables
-- Möser-Narayanan change labels: change = the output whose address clusters (multi-input) with
-- the inputs, revealed by a co-spend that lands inside the slice.
--
-- VALUE-CARRYING variant for examples/two_label_validation.py (optimal-change labeler needs min(input values)).
-- LEAN projection: only the columns the validation needs — version, locktime, input sequence, forward-spend
-- refs (spent_transaction_hash + index), addresses (inputs & outputs) + input & output values. Dropped
-- fee/weight/types/nested values -> far fewer bytes scanned (free-tier safe).
-- This slice is for the ordering/change validation, NOT for the type/uih/fee axes.
--
-- Filter on block_timestamp (partition column) with LITERAL timestamps so BigQuery prunes
-- partitions at plan time. IMPORTANT: do NOT use DECLARE variables here — a runtime variable
-- defeats pruning and the query scans the whole table (~780 GB -> blows the free quota). Edit the
-- two TIMESTAMP() literals in the WHERE clause to move/resize the window. 1 day ~= 144 blocks.
-- Widen the window to catch more reveals (change spent later); watch "bytes processed" first.
-- Export as NEWLINE-DELIMITED JSON (or a JSON array) to slice_values.json, then:
--   python3 examples/two_label_validation.py slice_values.json
--
-- Honest bias: only change spent WITHIN the window is revealed -> labels skew to fast-spending
-- wallets (services, peel chains). Widen the window to reduce it.

SELECT TO_JSON_STRING(STRUCT(
  t.hash AS txid,
  t.block_number AS height,
  t.version AS version,
  t.lock_time AS locktime,
  ARRAY(
    SELECT AS STRUCT
      i.spent_transaction_hash AS txid,
      i.spent_output_index      AS vout,
      i.sequence                AS sequence,
      STRUCT(
        i.value AS value,
        (SELECT a FROM UNNEST(i.addresses) a LIMIT 1) AS scriptpubkey_address
      ) AS prevout
    FROM UNNEST(t.inputs) i
  ) AS vin,
  ARRAY(
    SELECT AS STRUCT
      o.value AS value,
      (SELECT a FROM UNNEST(o.addresses) a LIMIT 1) AS scriptpubkey_address
    FROM UNNEST(t.outputs) o
  ) AS vout
)) AS row
FROM `bigquery-public-data.crypto_bitcoin.transactions` AS t
-- block_timestamp_month is the DATE partition column (name is misleading; granularity is DAY).
-- Filtering it is what prunes; block_timestamp then narrows within the day. Keep both in sync.
WHERE t.block_timestamp_month = DATE('2024-06-01')
  AND t.block_timestamp >= TIMESTAMP('2024-06-01') AND t.block_timestamp < TIMESTAMP('2024-06-02')
  AND t.is_coinbase = FALSE

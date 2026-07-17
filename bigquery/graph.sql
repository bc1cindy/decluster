-- Connected slice for the community-structure probe (graph_deanon.py): a contiguous
-- block range keeps the graph connected (a random sample would be disconnected).
-- The loader dedups by txid, so splitting a wide range across downloads is safe.
--
-- The table is partitioned by block_timestamp_month, not block_number. You MUST filter the
-- partition column itself (block_timestamp_month = '<first-of-month>'): a filter on
-- block_timestamp (the TIMESTAMP) does NOT prune the monthly partition and scans ~400 GB,
-- blowing the free 1 TB/month quota. With the partition filter each slice is ~0.25-4 GB.
-- The four eras in results/RESULTS-graph-deanon.md (move the month with the blocks):
--   2012: blocks 200000-200019 -> 2012-09   |   2013: 250000-250014 -> 2013-08
--   2016: blocks 400000-400004 -> 2016-02   |   2023: 800000-800002 -> 2023-07
SELECT
  `hash` AS txid,
  block_number AS height,
  ARRAY(
    SELECT AS STRUCT STRUCT(i.addresses[SAFE_OFFSET(0)] AS scriptpubkey_address) AS prevout
    FROM UNNEST(inputs) AS i
  ) AS vin,
  ARRAY(
    SELECT AS STRUCT o.addresses[SAFE_OFFSET(0)] AS scriptpubkey_address
    FROM UNNEST(outputs) AS o
  ) AS vout
FROM `bigquery-public-data.crypto_bitcoin.transactions`
WHERE block_timestamp_month = '2016-02-01'  -- partition prune: MUST be the partition column (move with the blocks)
  AND block_number BETWEEN 400000 AND 400004
  AND NOT is_coinbase

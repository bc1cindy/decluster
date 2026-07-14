-- Connected slice for the community-structure probe (graph_deanon.py): a contiguous
-- block range keeps the graph connected (a random sample would be disconnected).
-- The loader dedups by txid, so splitting a wide range across downloads is safe.
--
-- The table is partitioned by block_timestamp_month, not block_number: filtering by
-- block_number alone scans the whole table (~TB) and blows the free 1 TB/month quota.
-- The block_timestamp filter prunes to one partition (~GB). Move both together:
--   blocks 400000-400004 -> 2016-02   |   800000-800002 -> 2023-07
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
WHERE block_timestamp BETWEEN '2016-02-25' AND '2016-02-27'  -- partition prune (move with the blocks)
  AND block_number BETWEEN 400000 AND 400004
  AND NOT is_coinbase

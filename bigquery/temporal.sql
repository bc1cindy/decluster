-- Cluster temporal fingerprint calibration (broadcast.py: active_hours / schedule_distance).
-- Ground truth = address reuse: transactions spending the SAME input address are the same
-- owner (near-certain). For each input address reused >= 8 times over a WIDE window we collect
-- its txs' unix timestamps -> the owner's hour-of-day activity schedule.
--
-- A wide window (weeks) is essential: the daily/timezone cycle only shows over many days; a
-- one-day slice gives a null (all txs land in the same few hours). The table is partitioned by
-- block_timestamp_month, so keep the window inside one month to prune to one partition (~GB,
-- under the free 1 TB/month quota). Shrink to two weeks if the quota is tight.
--
-- Honest caveat: reused *input* addresses skew toward services/exchanges (active ~24/7, flat
-- schedules) rather than timezone-bound individuals, so this may under-show the effect. The
-- calibration reports whatever the data gives.
SELECT
  i.addresses[SAFE_OFFSET(0)] AS addr,
  ARRAY_AGG(UNIX_SECONDS(t.block_timestamp)) AS times
FROM `bigquery-public-data.crypto_bitcoin.transactions` AS t,
     UNNEST(t.inputs) AS i
WHERE t.block_timestamp >= TIMESTAMP('2024-01-01')
  AND t.block_timestamp <  TIMESTAMP('2024-02-01')          -- one month -> one partition
  AND i.addresses[SAFE_OFFSET(0)] IS NOT NULL
  AND NOT t.is_coinbase
GROUP BY addr
HAVING COUNT(*) >= 8
LIMIT 20000

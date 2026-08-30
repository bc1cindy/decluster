-- Neighbourhood persistence against view width. RESULTS-view-match-2026.md finds the
-- matcher's frontier collapses because only 14% of a vertex's neighbours in a one-day view
-- exist in the other view; the framework's mechanism needs recurring relationships. This
-- asks whether widening the view recovers them, at address level (union-find does not fit
-- in SQL, so this is a proxy for the cluster-level quantity).
--
-- Day 0 = block 939969. Views: A = days [0, w), B = days [7, 7+w). At w=7 they abut
-- without overlapping. Per-day bitmasks let every width come out of one aggregation.
WITH edge AS (
  SELECT DIV(block_number - 939969, 144) AS day, i AS a, o AS b
  FROM `bigquery-public-data.crypto_bitcoin.transactions`,
       UNNEST(ARRAY(SELECT DISTINCT x FROM UNNEST(inputs) v, UNNEST(v.addresses) x)) i,
       UNNEST(ARRAY(SELECT DISTINCT x FROM UNNEST(outputs) v, UNNEST(v.addresses) x)) o
  WHERE block_timestamp_month = '2026-03-01'
    AND block_number BETWEEN 939969 AND 941984
    AND NOT is_coinbase
),
undirected AS (
  SELECT LEAST(a, b) AS u, GREATEST(a, b) AS v, BIT_OR(1 << day) AS days
  FROM edge WHERE a != b GROUP BY u, v
),
vertex AS (
  SELECT u AS x, BIT_OR(days) AS days FROM (
    SELECT u, days FROM undirected UNION ALL SELECT v, days FROM undirected)
  GROUP BY x
),
w AS (SELECT * FROM UNNEST([1, 2, 3, 5, 7]) AS width),
mask AS (
  SELECT width,
         (1 << width) - 1                       AS ma,
         ((1 << width) - 1) << 7                AS mb
  FROM w
),
nb AS (
  SELECT m.width, e.u AS x, e.v AS y, vy.days AS ydays
  FROM undirected e JOIN mask m ON (e.days & m.ma) != 0
  JOIN vertex vy ON vy.x = e.v
  UNION ALL
  SELECT m.width, e.v AS x, e.u AS y, vx.days AS ydays
  FROM undirected e JOIN mask m ON (e.days & m.ma) != 0
  JOIN vertex vx ON vx.x = e.u
),
per_vertex AS (
  SELECT nb.width, nb.x,
         COUNT(DISTINCT nb.y) AS deg_a,
         COUNT(DISTINCT IF((nb.ydays & m.mb) != 0, nb.y, NULL)) AS surviving
  FROM nb JOIN mask m USING (width)
  GROUP BY width, x
),
core AS (
  SELECT p.width, p.x, p.deg_a, p.surviving
  FROM per_vertex p JOIN vertex vx ON vx.x = p.x JOIN mask m USING (width)
  WHERE p.deg_a >= 3 AND (vx.days & m.mb) != 0
)
SELECT width,
  COUNT(*) AS core_vertices,
  ROUND(AVG(deg_a), 2) AS mean_degree_a,
  ROUND(SUM(surviving) / SUM(deg_a), 4) AS neighbour_persistence,
  ROUND(AVG(IF(deg_a > 0, surviving / deg_a, 0)), 4) AS mean_per_vertex_persistence,
  COUNTIF(surviving >= 3) AS with_3plus_surviving
FROM core GROUP BY width ORDER BY width

-- 检查 5：维度取值脏数据。记下 <Other> / (data deleted) / (not set) 的占比，决定剔除还是归为 unknown
WITH v AS (
  SELECT 'channel' AS dim, channel AS val FROM `${PROJECT}.${DATASET}.dwd_events`
  UNION ALL SELECT 'device', device FROM `${PROJECT}.${DATASET}.dwd_events`
  UNION ALL SELECT 'country', country FROM `${PROJECT}.${DATASET}.dwd_events`
)
SELECT dim, IFNULL(val, 'NULL') AS val, COUNT(*) AS cnt,
  COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY dim) AS pct
FROM v
GROUP BY 1, 2
ORDER BY dim, cnt DESC;

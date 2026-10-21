-- 第 1 步 1c：维度新值 / 消失值检查（口径或埋点变更的信号）
WITH v AS (
  SELECT 'channel' AS dim, channel AS val, event_dt FROM `${PROJECT}.${DATASET}.dwd_events_clean`
    WHERE event_dt IN (@cur_dt, @base_dt)
  UNION ALL SELECT 'device', device, event_dt FROM `${PROJECT}.${DATASET}.dwd_events_clean`
    WHERE event_dt IN (@cur_dt, @base_dt)
  UNION ALL SELECT 'country', country, event_dt FROM `${PROJECT}.${DATASET}.dwd_events_clean`
    WHERE event_dt IN (@cur_dt, @base_dt)
)
SELECT dim, val,
  COUNTIF(event_dt = @cur_dt)  AS cur_cnt,
  COUNTIF(event_dt = @base_dt) AS base_cnt
FROM v
GROUP BY dim, val
HAVING cur_cnt = 0 OR base_cnt = 0
ORDER BY dim, cur_cnt + base_cnt DESC;

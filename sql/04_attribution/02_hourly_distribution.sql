-- 第 1 步 1b：小时分布，检查数据延迟 / 截断（某个小时之后量几乎为 0）
SELECT
  EXTRACT(HOUR FROM TIMESTAMP_MICROS(event_timestamp)) AS hr,
  COUNTIF(event_dt = @cur_dt)  AS cur_cnt,
  COUNTIF(event_dt = @base_dt) AS base_cnt
FROM `${PROJECT}.${DATASET}.dwd_events_clean`
WHERE event_dt IN (@cur_dt, @base_dt)
GROUP BY hr
ORDER BY hr;

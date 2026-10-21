-- 第 1 步 1a'：按操作系统切片的事件结构对比。埋点问题常常只出现在某一端（如 iOS）
WITH d AS (
  SELECT os, event_name,
    COUNTIF(event_dt = @cur_dt)  AS cur_cnt,
    COUNTIF(event_dt = @base_dt) AS base_cnt
  FROM `${PROJECT}.${DATASET}.dwd_events_clean`
  WHERE event_dt IN (@cur_dt, @base_dt)
  GROUP BY os, event_name
)
SELECT *, SAFE_DIVIDE(cur_cnt, base_cnt) - 1 AS chg
FROM d
WHERE base_cnt >= 20   -- 离群判断只看 >= 50 的事件，20~50 的只用来判断下游是否跟着变
ORDER BY os, ABS(SAFE_DIVIDE(cur_cnt, base_cnt) - 1) DESC;

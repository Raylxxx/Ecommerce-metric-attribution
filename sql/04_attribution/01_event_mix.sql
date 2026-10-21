-- 第 1 步 1a：事件结构对比，哪个事件变化异常大
-- 参数：@cur_dt 当前期，@base_dt 基准期（DATE）
-- 判定：单一事件偏离远大于其他事件、且它下游的事件没有跟着变 → 疑似埋点丢失
WITH d AS (
  SELECT event_name,
    COUNTIF(event_dt = @cur_dt)  AS cur_cnt,
    COUNTIF(event_dt = @base_dt) AS base_cnt
  FROM `${PROJECT}.${DATASET}.dwd_events_clean`
  WHERE event_dt IN (@cur_dt, @base_dt)
  GROUP BY event_name
)
SELECT *, SAFE_DIVIDE(cur_cnt, base_cnt) - 1 AS chg
FROM d
WHERE base_cnt >= 20   -- 离群判断只看 >= 50 的事件，20~50 的只用来判断下游是否跟着变
ORDER BY ABS(SAFE_DIVIDE(cur_cnt, base_cnt) - 1) DESC;

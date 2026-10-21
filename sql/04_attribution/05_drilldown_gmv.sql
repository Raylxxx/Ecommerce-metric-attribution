-- 第 3 步 方法 A：GMV 可加，直接按维度组合分，按 |ΔGMV| 排序
SELECT channel, device, country,
  SUM(IF(event_dt = @base_dt, gmv, 0)) AS g0,
  SUM(IF(event_dt = @cur_dt,  gmv, 0)) AS g1,
  SUM(IF(event_dt = @cur_dt,  gmv, 0)) - SUM(IF(event_dt = @base_dt, gmv, 0)) AS delta,
  SAFE_DIVIDE(
    SUM(IF(event_dt = @cur_dt, gmv, 0)) - SUM(IF(event_dt = @base_dt, gmv, 0)),
    SUM(SUM(IF(event_dt = @cur_dt, gmv, 0)) - SUM(IF(event_dt = @base_dt, gmv, 0))) OVER ()) AS share_of_change
FROM `${PROJECT}.${DATASET}.ads_daily_metrics`
WHERE event_dt IN (@base_dt, @cur_dt)
GROUP BY 1, 2, 3
ORDER BY ABS(delta) DESC
LIMIT 10;

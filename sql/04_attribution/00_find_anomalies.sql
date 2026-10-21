-- 找异动点：按 z 值排序，选案例、也用来挑评测注入的「平静日期」（|z| < 1）
SELECT event_dt, gmv, gmv_wow,
  (gmv - gmv_ma28) / NULLIF(gmv_sd28, 0) AS z
FROM `${PROJECT}.${DATASET}.ads_daily_anomaly`
WHERE gmv_sd28 IS NOT NULL
ORDER BY ABS((gmv - gmv_ma28) / NULLIF(gmv_sd28, 0)) DESC
LIMIT 15;

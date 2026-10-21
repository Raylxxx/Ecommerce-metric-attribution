-- 校验 2：恒等式 UV × CR × AOV = GMV，期望返回 0 行
SELECT event_dt, gmv,
  uv * SAFE_DIVIDE(orders, uv) * SAFE_DIVIDE(gmv, orders) AS gmv_rebuilt
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE orders > 0
  AND ABS(gmv - uv * SAFE_DIVIDE(orders, uv) * SAFE_DIVIDE(gmv, orders)) > 0.01;

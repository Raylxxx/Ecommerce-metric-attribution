-- 对数校验（建完汇总表必须跑，两条都通过才继续）
-- 校验 1：汇总表 GMV 与明细表 GMV 一致
SELECT
  (SELECT SUM(gmv) FROM `${PROJECT}.${DATASET}.ads_daily_metrics`)            AS ads_metrics_gmv,
  (SELECT SUM(gmv) FROM `${PROJECT}.${DATASET}.ads_daily_total`)              AS ads_total_gmv,
  (SELECT SUM(revenue) FROM `${PROJECT}.${DATASET}.dwd_events_clean`
     WHERE event_name = 'purchase')                                            AS dwd_gmv;

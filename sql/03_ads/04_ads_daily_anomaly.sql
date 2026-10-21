-- 异动标记表：在 SQL 里算好，Tableau 只负责显示
-- 数据只有 3 个月，没有去年同期，所以「同比」用周同比（对比上周同一天），「环比」用日环比
CREATE OR REPLACE TABLE `${PROJECT}.${DATASET}.ads_daily_anomaly` AS
SELECT *,
  SAFE_DIVIDE(gmv, LAG(gmv, 1) OVER w) - 1                                         AS gmv_dod,
  SAFE_DIVIDE(gmv, LAG(gmv, 7) OVER w) - 1                                         AS gmv_wow,
  AVG(gmv)    OVER (ORDER BY event_dt ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING)   AS gmv_ma28,
  STDDEV(gmv) OVER (ORDER BY event_dt ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING)   AS gmv_sd28
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WINDOW w AS (ORDER BY event_dt);
-- Tableau 计算字段：is_anomaly = ABS([Gmv] - [Gmv Ma28]) > 2 * [Gmv Sd28]

-- 清洗前后对比：每条规则剔除了多少，写进埋点评审报告
SELECT
  (SELECT COUNT(*) FROM `${PROJECT}.${DATASET}.dwd_events`)                                   AS rows_raw,
  (SELECT COUNT(*) FROM `${PROJECT}.${DATASET}.dwd_events_clean`)                             AS rows_clean,
  (SELECT COUNTIF(event_name = 'purchase') FROM `${PROJECT}.${DATASET}.dwd_events`)           AS purchase_raw,
  (SELECT COUNTIF(event_name = 'purchase') FROM `${PROJECT}.${DATASET}.dwd_events_clean`)     AS purchase_clean,
  (SELECT SUM(IF(event_name = 'purchase', revenue, 0)) FROM `${PROJECT}.${DATASET}.dwd_events`)       AS gmv_raw,
  (SELECT SUM(IF(event_name = 'purchase', revenue, 0)) FROM `${PROJECT}.${DATASET}.dwd_events_clean`) AS gmv_clean;

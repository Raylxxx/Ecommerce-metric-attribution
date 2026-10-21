-- 明细表 dwd_events：只取后续要用的列，按日期分区
-- 这一步扫一次公共数据集，之后所有查询都走自己的表，省额度
CREATE OR REPLACE TABLE `${PROJECT}.${DATASET}.dwd_events`
PARTITION BY event_dt AS
SELECT
  PARSE_DATE('%Y%m%d', event_date)                                         AS event_dt,
  event_timestamp,
  event_name,
  user_pseudo_id,
  (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
  device.category                                                          AS device,
  device.operating_system                                                  AS os,
  geo.country                                                              AS country,
  traffic_source.medium                                                    AS channel,   -- 首次获客媒介，不是会话渠道
  ecommerce.transaction_id                                                 AS transaction_id,
  ecommerce.purchase_revenue_in_usd                                        AS revenue,
  ecommerce.total_item_quantity                                            AS item_qty
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131';

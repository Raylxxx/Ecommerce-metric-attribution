---
metric_id: orders
name_cn: 订单数
level: L2
parent: gmv
children: []
unit: 单
owner: 扬
updated: 待定稿
---

## 定义
当日去重 `transaction_id` 数（清洗后）。辅助指标，用于算 CR 和 AOV。

## 业务含义
成交笔数，CR 的分子、AOV 的分母。

## 计算 SQL
```sql
SELECT event_dt, orders
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt;
```

## 可拆分维度
channel / device / country 可拆，订单数可加。

## 注意事项 / 常见错误
- 不要用 purchase 事件数代替订单数：同一订单会被重复上报。
- 没有订单号（NULL / '(not set)'）的下单事件在清洗时已剔除，剔除比例见 docs/tracking_review.md。

## 校验
COUNT(DISTINCT transaction_id) = 清洗表 purchase 事件行数（清洗后每单只剩一条）。

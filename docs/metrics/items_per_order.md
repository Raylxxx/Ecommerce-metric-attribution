---
metric_id: items_per_order
name_cn: 每单件数
level: L3
parent: aov
children: []
unit: 件 / 单
owner: 扬
updated: 待定稿
---

## 定义
商品件数（`total_item_quantity` 之和） / 订单数。

## 业务含义
AOV 的子因子之一：每单买几件。

## 计算 SQL
```sql
SELECT event_dt, SAFE_DIVIDE(SUM(items), SUM(orders)) AS items_per_order
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country 可拆。

## 注意事项 / 常见错误
- total_item_quantity 在混淆数据里偶尔为空，汇总时按 0 处理，会让件数偏低。

## 校验
每单件数 × 件单价 = AOV。

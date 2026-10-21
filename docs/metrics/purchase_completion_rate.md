---
metric_id: purchase_completion_rate
name_cn: 下单完成率
level: L3
parent: conversion_rate
children: []
unit: 比例（%）
owner: 扬
updated: 待定稿
---

## 定义
下单用户数（触发 `purchase`） / 触发 `begin_checkout` 的用户数。

## 业务含义
漏斗最后一步：开始结算的人有没有真正付款。

## 计算 SQL
```sql
SELECT event_dt, SAFE_DIVIDE(SUM(buyer_uv), SUM(checkout_uv)) AS purchase_completion_rate
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country / os 可拆。

## 注意事项 / 常见错误
- 混淆数据里存在「有下单无结算」的用户，这个比率可能 > 100%，要在报告里说明。
- 支付方式故障一般表现为这一环节单独下降。
- LMDI 往下拆 CR 时还有一项「人均订单数」(orders / buyer_uv)，不要漏掉，否则子因子之和对不上。

## 校验
浏览率 × 加购率 × 结算率 × 下单完成率 × 人均订单数 = CR。

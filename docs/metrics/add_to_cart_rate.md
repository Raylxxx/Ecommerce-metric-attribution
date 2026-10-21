---
metric_id: add_to_cart_rate
name_cn: 加购率
level: L3
parent: conversion_rate
children: []
unit: 比例（%）
owner: 扬
updated: 待定稿
---

## 定义
触发 `add_to_cart` 的用户数 / 触发 `view_item` 的用户数。

## 业务含义
漏斗第二步：看了商品的人有没有加购。

## 计算 SQL
```sql
SELECT event_dt, SAFE_DIVIDE(SUM(cart_uv), SUM(view_uv)) AS add_to_cart_rate
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country / os 可拆。

## 注意事项 / 常见错误
- 分母是浏览商品的用户，不是 UV。
- 埋点问题常常只出现在某一端（例如 iOS 的 add_to_cart 不上报），排假时要按 os 切片看。

## 校验
cart_uv 一般 ≤ view_uv，不成立的比例写进埋点评审。

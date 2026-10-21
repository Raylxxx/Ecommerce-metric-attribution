---
metric_id: aov
name_cn: 客单价
level: L2
parent: gmv
children: [items_per_order, avg_item_price]
unit: 美元 / 单
owner: 扬
updated: 待定稿
---

## 定义
GMV / 订单数。

## 业务含义
衡量「每单买多少钱」，GMV = UV × CR × AOV 的第三个因子；可继续拆成 每单件数 × 件单价。

## 计算 SQL
```sql
SELECT event_dt, SAFE_DIVIDE(SUM(gmv), SUM(orders)) AS aov
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country 可拆；AOV 是比率，下钻权重用订单占比，同样要拆转化效应和结构效应。

## 注意事项 / 常见错误
- 这里的客单价是「每单金额」，不是「人均消费」（GMV / 下单用户数），两者不要混用。
- 单日订单少时 AOV 受个别大单影响很大，结论要看连续几天。
- 不能用 AVG(分组 AOV) 当总体 AOV。

## 校验
AOV × 订单数 = GMV。

---
metric_id: gmv
name_cn: GMV（成交额）
level: L1
parent: 
children: [uv, conversion_rate, aov]
unit: 美元（USD）
owner: 扬
updated: 待定稿
---

## 定义
清洗后下单事件 `purchase_revenue_in_usd`（落表后字段名 `revenue`）之和。清洗规则：订单号去重、剔除无订单号和金额 ≤ 0 的下单事件。

## 业务含义
最顶层的结果指标。恒等式 GMV = UV × CR × AOV，异动归因从它开始拆。

## 计算 SQL
```sql
SELECT event_dt, gmv
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
ORDER BY event_dt;
```

## 可拆分维度
channel / device / country 都可拆，**GMV 可加**：各分组 GMV 之和 = 总 GMV，下钻可以直接按分组差值排序（方法 A）。

## 注意事项 / 常见错误
- 必须用清洗表 dwd_events_clean 或汇总表，不能直接对原始表求和（原始表有重复上报的订单）。
- 金额字段用 purchase_revenue_in_usd，不要用 purchase_revenue（币种不统一）。
- 比较两期 GMV 时要写清基准期：默认是「上周同一天」，不是「前一天」。
- 数据只有 2020-11-01 ~ 2021-01-31，没有去年同期，不能做真正的年同比。

## 校验
`ads_daily_metrics` 的 GMV 合计 = `ads_daily_total` 的 GMV 合计 = 明细表 purchase 金额合计（sql/03_ads/90_reconcile.sql）。

# ① Tableau 经营看板

**Tableau Public 链接**：待发布后填写

## 数据怎么进 Tableau Public

Tableau Public 不能直连 BigQuery，所以我先在 BigQuery 里把看板专用的小表建好，再导出 CSV：

```bash
python scripts/export_dashboard_csv.py            # 从 BigQuery 导出到 dashboard/data/
python scripts/export_dashboard_csv.py --offline  # 先用合成数据导一份，在 Tableau 里把布局搭好
```

| 文件 | 来源 SQL | 用途 |
|---|---|---|
| ads_daily_total.csv | sql/03_ads/03_ads_daily_total.sql | KPI 卡片、趋势 |
| ads_daily_metrics.csv | sql/03_ads/02_ads_daily_metrics.sql | 筛选、下钻热力图 |
| ads_daily_anomaly.csv | sql/03_ads/04_ads_daily_anomaly.sql | 异动红点、28 日均线 |
| ads_funnel_long.csv | sql/03_ads/05_ads_funnel_long.sql | 5 步漏斗 |

## 页面布局

**页面 1：经营总览**
```
┌─────────────────────────────────────────────┐
│ 筛选：日期范围 | 渠道 | 设备 | 国家           │
├──────────┬──────────┬──────────┬────────────┤
│ GMV 卡片 │ UV 卡片  │ CR 卡片  │ AOV 卡片    │  ← 数值 + 周同比箭头
├──────────┴──────────┴──────────┴────────────┤
│ GMV 日趋势 + 异动点（红点）+ 28 日均线         │
├──────────────────────┬──────────────────────┤
│ 转化漏斗（5 步）       │ UV / CR / AOV 小折线   │
└──────────────────────┴──────────────────────┘
```

**页面 2：维度下钻**
- 渠道 × 设备热力图（颜色 = CR 周同比变化，单位 pp）
- 国家条形图（GMV 周同比变化贡献）

## 关键计算字段

```
// 总体 CR：不要用 AVG(分组 CR)
SUM([Orders]) / SUM([Uv])

// AOV
SUM([Gmv]) / SUM([Orders])

// 异动标记
IF ABS([Gmv] - [Gmv Ma28]) > 2 * [Gmv Sd28] THEN "异动" ELSE "正常" END
```

> 注意：在「日 × 维度」表上筛选后，UV 用 SUM 会比真实去重 UV 偏大（同一用户跨设备），
> 总览页的 UV 卡片固定从 ads_daily_total 取。

## 同比口径
数据只有 3 个月，没有去年同期，「同比」用周同比（对比上周同一天），「环比」用日环比。

## 验收
- [ ] 看板数字与 SQL 结果抽查 3 个日期一致
- [ ] 截图放 `screenshots/`：overview.png、drilldown.png、funnel.png

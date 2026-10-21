# 项目：电商指标异动归因 + AI 归因助手

## 数据
- BigQuery 数据集：`${GCP_PROJECT_ID}.ga4_attr`（评测时为 `ga4_eval`，表名带 `case_xxx_` 前缀，以 `describe_tables` 返回为准）
- 范围：2020-11-01 ~ 2021-01-31（Google Merchandise Store GA4 混淆样本）
- 表：
  - `dwd_events_clean`：清洗后事件明细，按 `event_dt` 分区
  - `ads_daily_metrics`：日 × channel × device × country
  - `ads_daily_total`：日总体（总体 UV / CR / AOV 只从这里取）

## 口径要点
- GMV = UV × CR × AOV，CR = 订单数 / UV，AOV = GMV / 订单数（订单口径）
- channel = 首次获客媒介（traffic_source.medium），不是会话渠道
- UV 跨维度、跨天都不可加；GMV、订单数可加
- 转化率变化用 pp 表示
- 完整口径在 `docs/metrics/`，通过 MCP 工具 `search_metric_doc` 检索

## 工作方式
- 任何「某指标为什么涨/跌」「异动原因」类问题，一律使用 `metric-attribution` skill
- 查数只用 `bq-attribution` MCP 的 `run_sql`（只读）；所有 SQL 都要按 `event_dt` 过滤
- 每次分析的中间结果写到 `runs/<YYYYMMDD-HHMM>/`
- SQL 模板在 `sql/04_attribution/`，里面的 `${PROJECT}.${DATASET}` 要替换成 `describe_tables` 返回的全名，`@cur_dt` / `@base_dt` 替换成 `DATE 'YYYY-MM-DD'`

## 代码
- Python 归因库：`attribution/`，测试：`pytest`
- 改了 SQL 口径要同步改 `attribution/metrics.py`，并跑 `python scripts/verify_sql_local.py`

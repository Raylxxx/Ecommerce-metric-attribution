"""bq-attribution：给 Claude Code 用的 MCP 服务器。

工具清单：
- describe_tables      当前可用的表和字段（评测时会切到 ga4_eval 数据集 + case 前缀）
- list_metrics         指标清单
- search_metric_doc    检索口径文档（写 SQL 之前必须先调）
- get_metric_doc       取某个指标的完整口径
- run_sql              只读 BigQuery 查询，带扫描量上限

我自己写而没直接用现成的 BigQuery MCP，主要是为了加护栏：
只读、单语句、限制扫描量、提醒分区过滤，并把口径检索和查数放在同一个服务里。

启动：python mcp_server/server.py（stdio），在 .mcp.json 里注册。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp_server.retriever import MetricDocRetriever  # noqa: E402
from mcp_server.sql_guard import check_sql, has_partition_filter  # noqa: E402

try:  # mcp 2.x 把 FastMCP 改名成了 MCPServer，两种版本都兼容
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server

PROJECT = os.environ.get("GCP_PROJECT_ID", "")
DATASET = os.environ.get("BQ_DATASET", "ga4_attr")
TABLE_PREFIX = os.environ.get("BQ_TABLE_PREFIX", "")         # 评测时形如 case_017_
MAX_BYTES = int(float(os.environ.get("BQ_MAX_BYTES", 2e9)))  # 单次最多扫描 2GB
MAX_ROWS_CAP = 1000

TABLES = {
    "dwd_events_clean": "清洗后事件明细，按 event_dt 分区。字段：event_dt, event_timestamp, event_name, "
                        "user_pseudo_id, session_id, device, os, country, channel, transaction_id, revenue, item_qty",
    "ads_daily_metrics": "日 × channel × device × country 汇总。字段：uv, new_uv, view_uv, cart_uv, checkout_uv, "
                         "buyer_uv, orders, gmv, items（UV 类字段跨维度不可加）",
    "ads_daily_total": "日汇总，总体指标一律从这里取。字段同上，另有 cr, aov",
}

mcp = _Server("bq-attribution")
retriever = MetricDocRetriever(ROOT / "docs" / "metrics")
_client = None


def _bq():
    global _client
    if _client is None:
        from google.cloud import bigquery
        _client = bigquery.Client(project=PROJECT or None)
    return _client


def full_name(table: str) -> str:
    return f"`{PROJECT}.{DATASET}.{TABLE_PREFIX}{table}`"


@mcp.tool()
def describe_tables() -> str:
    """返回本次可用的表全名和字段说明。写 SQL 前先调用一次，表名以这里返回的为准。"""
    lines = [f"数据集：{PROJECT}.{DATASET}，表前缀：{TABLE_PREFIX or '(无)'}"]
    lines += [f"- {full_name(t)}：{desc}" for t, desc in TABLES.items()]
    lines.append("数据范围 2020-11-01 ~ 2021-01-31；channel = 首次获客媒介，不是会话渠道。")
    return "\n".join(lines)


@mcp.tool()
def list_metrics() -> str:
    """列出口径文档里的全部指标（metric_id、中文名、层级、父指标）。"""
    return "\n".join(f"{m['metric_id']}\t{m['name_cn']}\t{m['level']}\tparent={m['parent']}"
                     for m in retriever.list_metrics())


@mcp.tool()
def search_metric_doc(query: str, top_k: int = 3) -> str:
    """检索《指标口径文档》。写任何 SQL 之前先调用，确认定义、分母、可拆维度和常见错误。"""
    return retriever.search(query, max(1, min(top_k, 8)))


@mcp.tool()
def get_metric_doc(metric_id: str) -> str:
    """按 metric_id（如 conversion_rate）返回完整口径文档。"""
    return retriever.get(metric_id)


@mcp.tool()
def run_sql(sql: str, max_rows: int = 200) -> str:
    """在 BigQuery 上执行只读 SQL，返回 CSV。只允许单条 SELECT / WITH；
    单次扫描超过上限会直接失败。请用 event_dt 过滤分区，表名用 describe_tables 返回的全名。"""
    ok, reason = check_sql(sql)
    if not ok:
        return f"ERROR: {reason}"
    from google.cloud import bigquery

    client = _bq()
    # 先 dry run 估算扫描量，超限就不真正执行，给出可读的报错
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    if (dry.total_bytes_processed or 0) > MAX_BYTES:
        return (f"ERROR: 预计扫描 {dry.total_bytes_processed / 1e9:.2f} GB，超过上限 {MAX_BYTES / 1e9:.1f} GB。"
                "请加 event_dt 过滤或改查汇总表。")
    job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=MAX_BYTES))
    df = job.result(max_results=max(1, min(max_rows, MAX_ROWS_CAP))).to_dataframe()
    gb = (job.total_bytes_processed or 0) / 1e9
    note = "" if has_partition_filter(sql) else "\n-- 提醒：这条查询没有按 event_dt 过滤"
    return f"-- scanned {gb:.3f} GB, rows={len(df)}{note}\n" + df.to_csv(index=False)


if __name__ == "__main__":
    mcp.run()

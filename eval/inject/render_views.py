"""把每个用例渲染成 BigQuery 视图：case_xxx_dwd_events_clean / _ads_daily_metrics / _ads_daily_total。

用视图而不是复制大表：50 个用例 × 一张明细表太占存储，视图只在查询时计算。
抽样用 FARM_FINGERPRINT(case_id + user_pseudo_id) 做确定性分桶，每次结果一致。

    python eval/inject/render_views.py              # 只生成 SQL 到 eval/inject/sql/
    python eval/inject/render_views.py --execute    # 生成并在 BigQuery 上创建视图
"""

from __future__ import annotations

import argparse
import os
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from eval.inject.generate_cases import CASES_DIR, read_jsonl  # noqa: E402

OUT_DIR = ROOT / "eval" / "inject" / "sql"
SRC = "`${PROJECT}.${DATASET}.dwd_events_clean`"
CHECKOUT_AND_AFTER = "('begin_checkout', 'add_shipping_info', 'add_payment_info', 'purchase')"


def _seg_cond(seg: dict | None, alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    return " AND ".join(f"{p}{k} = '{v}'" for k, v in (seg or {}).items()) or "TRUE"


def _bucket(cid: str, pct: int, col: str = "user_pseudo_id") -> str:
    return f"MOD(ABS(FARM_FINGERPRINT(CONCAT('{cid}', {col}))), 100) < {pct}"


def events_view_sql(case: dict) -> str:
    cid, t, dt = case["case_id"], case["type"], case["date"]
    pct = int(round((case.get("magnitude") or 0) * 100))
    target = "`${PROJECT}.${EVAL_DATASET}." + cid + "_dwd_events_clean`"
    head = f"-- {cid}: {t} {dt} segment={case.get('segment')} magnitude={case.get('magnitude')} params={case.get('params')}\n"
    head += f"CREATE OR REPLACE VIEW {target} AS\n"
    seg = _seg_cond(case.get("segment"))

    if t == "control":
        body = f"SELECT * FROM {SRC}"
    elif t == "traffic":
        body = (f"WITH affected AS (\n  SELECT DISTINCT user_pseudo_id FROM {SRC}\n"
                f"  WHERE event_dt = '{dt}' AND {seg} AND {_bucket(cid, pct)}\n)\n"
                f"SELECT * FROM {SRC}\nWHERE NOT (event_dt = '{dt}' AND user_pseudo_id IN (SELECT user_pseudo_id FROM affected))")
    elif t == "conversion":
        body = (f"WITH affected AS (\n  SELECT DISTINCT user_pseudo_id FROM {SRC}\n"
                f"  WHERE event_dt = '{dt}' AND {seg} AND event_name = 'purchase' AND {_bucket(cid, pct)}\n)\n"
                f"SELECT * FROM {SRC}\nWHERE NOT (event_dt = '{dt}' AND {seg}\n"
                f"  AND user_pseudo_id IN (SELECT user_pseudo_id FROM affected)\n"
                f"  AND event_name IN {CHECKOUT_AND_AFTER})")
    elif t == "aov":
        factor = round(1 - case["magnitude"], 4)
        body = (f"SELECT * REPLACE(\n  IF(event_dt = '{dt}' AND event_name = 'purchase' AND {seg}, revenue * {factor}, revenue) AS revenue)\n"
                f"FROM {SRC}")
    elif t == "tracking_loss":
        p = case["params"]
        os_cond = f" AND os = '{p['os']}'" if p.get("os") else ""
        key = "CONCAT(user_pseudo_id, CAST(event_timestamp AS STRING))"
        body = (f"SELECT * FROM {SRC}\nWHERE NOT (event_dt = '{dt}' AND event_name = '{p['event']}'{os_cond}\n"
                f"  AND {_bucket(cid, pct, key)})")
    elif t == "delay":
        h = case["params"]["hour"]
        body = (f"SELECT * FROM {SRC}\nWHERE NOT (event_dt = '{dt}'\n"
                f"  AND EXTRACT(HOUR FROM TIMESTAMP_MICROS(event_timestamp)) >= {h})")
    else:
        raise ValueError(t)
    return head + body + ";\n"


def ads_view_sql(case: dict, table: str) -> str:
    """复用 sql/03_ads 的建表 SQL，只把源表换成用例视图、把 TABLE 换成 VIEW，保证口径完全一致。"""
    src = (ROOT / "sql" / "03_ads" / {"ads_daily_metrics": "02_ads_daily_metrics.sql",
                                       "ads_daily_total": "03_ads_daily_total.sql"}[table]).read_text(encoding="utf-8")
    cid = case["case_id"]
    src = src.replace(SRC, "`${PROJECT}.${EVAL_DATASET}." + cid + "_dwd_events_clean`")
    src = src.replace(f"CREATE OR REPLACE TABLE `${{PROJECT}}.${{DATASET}}.{table}`\nPARTITION BY event_dt AS",
                      f"CREATE OR REPLACE VIEW `${{PROJECT}}.${{EVAL_DATASET}}.{cid}_{table}` AS")
    return src


def render_case(case: dict, project: str, dataset: str = "ga4_attr", eval_dataset: str = "ga4_eval") -> list[str]:
    stmts = [events_view_sql(case), ads_view_sql(case, "ads_daily_metrics"), ads_view_sql(case, "ads_daily_total")]
    return [string.Template(s).safe_substitute(PROJECT=project, DATASET=dataset, EVAL_DATASET=eval_dataset)
            for s in stmts]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--cases", default=str(CASES_DIR / "ground_truth.jsonl"))
    a = ap.parse_args()
    project = os.environ.get("GCP_PROJECT_ID", "ecom-attribution")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = None
    if a.execute:
        from google.cloud import bigquery
        client = bigquery.Client(project=project)
        client.create_dataset(f"{project}.ga4_eval", exists_ok=True)
    for case in read_jsonl(Path(a.cases)):
        stmts = render_case(case, project)
        (OUT_DIR / f"{case['case_id']}.sql").write_text("\n".join(stmts), encoding="utf-8")
        if client:
            for s in stmts:
                client.query(s).result()
            print(f"[created] {case['case_id']}")
    print(f"SQL 已写到 {OUT_DIR}")


if __name__ == "__main__":
    main()

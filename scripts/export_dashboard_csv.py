"""把看板要用的 4 张表导出成 CSV（Tableau Public 不能直连 BigQuery，只能连文件）。

    python scripts/export_dashboard_csv.py            # 导到 dashboard/data/
    python scripts/export_dashboard_csv.py --offline  # 用合成数据导一份，先在 Tableau 里搭布局
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "dashboard" / "data"
TABLES = ["ads_daily_total", "ads_daily_metrics", "ads_daily_anomaly", "ads_funnel_long"]


def export_bigquery() -> None:
    from google.cloud import bigquery
    from scripts.bq_build import load_env

    load_env()
    project, dataset = os.environ["GCP_PROJECT_ID"], os.environ.get("BQ_DATASET", "ga4_attr")
    client = bigquery.Client(project=project)
    for t in TABLES:
        df = client.query(f"SELECT * FROM `{project}.{dataset}.{t}` ORDER BY 1").to_dataframe()
        df.to_csv(OUT / f"{t}.csv", index=False, encoding="utf-8")
        print(f"{t}: {len(df)} 行")


def export_offline() -> None:
    import pandas as pd

    from attribution.metrics import clean_events, daily_total, daily_by_dims, map_top_countries
    from attribution.synthetic import generate_events

    ev, _ = clean_events(generate_events())
    total = daily_total(ev)
    dims = daily_by_dims(map_top_countries(ev))
    anomaly = total.sort_values("event_dt").copy()
    anomaly["gmv_dod"] = anomaly["gmv"] / anomaly["gmv"].shift(1) - 1
    anomaly["gmv_wow"] = anomaly["gmv"] / anomaly["gmv"].shift(7) - 1
    anomaly["gmv_ma28"] = anomaly["gmv"].shift(1).rolling(28, min_periods=7).mean()
    anomaly["gmv_sd28"] = anomaly["gmv"].shift(1).rolling(28, min_periods=7).std()
    steps = [(1, "访问", "uv"), (2, "浏览商品", "view_uv"), (3, "加购", "cart_uv"),
             (4, "结算", "checkout_uv"), (5, "下单", "buyer_uv")]
    funnel = pd.concat([
        dims[["event_dt", "channel", "device", "country"]].assign(step_order=o, step_name=n, users=dims[c])
        for o, n, c in steps
    ])
    for name, df in zip(TABLES, [total, dims, anomaly, funnel]):
        df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8")
        print(f"{name}: {len(df)} 行（合成数据）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    export_offline() if a.offline else export_bigquery()

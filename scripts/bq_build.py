"""按顺序在 BigQuery 上建表：明细 → 清洗 → 汇总 → 对数校验。

用法：
    python scripts/bq_build.py                 # 全部建一遍
    python scripts/bq_build.py --only 03_ads   # 只跑某个目录
    python scripts/bq_build.py --dry-run       # 只估算扫描量，不执行

需要先 `gcloud auth application-default login`，并在 .env 里填好 GCP_PROJECT_ID。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sql_template import render  # noqa: E402

# 建表顺序。02_dq_checks 是只读检查，单独跑：python scripts/run_sql.py sql/02_dq_checks/xxx.sql
BUILD_ORDER = [
    "sql/01_dwd/01_dwd_events.sql",
    "sql/01_dwd/02_dwd_events_clean.sql",
    "sql/03_ads/01_top_countries.sql",
    "sql/03_ads/02_ads_daily_metrics.sql",
    "sql/03_ads/03_ads_daily_total.sql",
    "sql/03_ads/04_ads_daily_anomaly.sql",
    "sql/03_ads/05_ads_funnel_long.sql",
]
CHECKS = ["sql/03_ads/90_reconcile.sql", "sql/03_ads/91_identity_check.sql"]


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑路径里包含这个字符串的文件")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load_env()
    from google.cloud import bigquery

    client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])
    files = [f for f in BUILD_ORDER + CHECKS if not args.only or args.only in f]
    for f in files:
        sql = render(ROOT / f)
        cfg = bigquery.QueryJobConfig(dry_run=args.dry_run, use_query_cache=False)
        job = client.query(sql, job_config=cfg)
        if args.dry_run:
            print(f"[dry-run] {f}: 预计扫描 {job.total_bytes_processed / 1e9:.3f} GB")
            continue
        rows = list(job.result())
        print(f"[done] {f}: 扫描 {(job.total_bytes_processed or 0) / 1e9:.3f} GB")
        if f in CHECKS:
            for r in rows:
                print("   ", dict(r))
            if f.endswith("91_identity_check.sql") and rows:
                print("    ⚠️ 恒等式校验没通过，先别往下做")


if __name__ == "__main__":
    main()

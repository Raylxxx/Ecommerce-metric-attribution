"""跑单个 SQL 文件并把结果存成 CSV，归因 SQL 的日期参数从命令行传。

    python scripts/run_sql.py sql/04_attribution/04_lmdi.sql --cur 2020-12-28 --base 2020-12-21
    python scripts/run_sql.py sql/02_dq_checks/03_purchase_txn_consistency.sql -o docs/dq/txn.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.bq_build import load_env  # noqa: E402
from scripts.sql_template import render  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sql_file")
    ap.add_argument("--cur", help="当前期日期 YYYY-MM-DD，对应 @cur_dt")
    ap.add_argument("--base", help="基准期日期 YYYY-MM-DD，对应 @base_dt")
    ap.add_argument("-o", "--output", help="结果存成 CSV")
    ap.add_argument("--max-gb", type=float, default=2.0, help="单次最多扫描多少 GB，超了直接报错")
    args = ap.parse_args()

    load_env()
    from google.cloud import bigquery

    client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])
    params = []
    if args.cur:
        params.append(bigquery.ScalarQueryParameter("cur_dt", "DATE", args.cur))
    if args.base:
        params.append(bigquery.ScalarQueryParameter("base_dt", "DATE", args.base))
    cfg = bigquery.QueryJobConfig(query_parameters=params,
                                  maximum_bytes_billed=int(args.max_gb * 1e9))
    job = client.query(render(ROOT / args.sql_file), job_config=cfg)
    df = job.result().to_dataframe()
    print(f"-- 扫描 {(job.total_bytes_processed or 0) / 1e9:.3f} GB，{len(df)} 行")
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.output, index=False, encoding="utf-8")
        print(f"已保存到 {args.output}")
    else:
        print(df.to_string(max_rows=50))


if __name__ == "__main__":
    main()

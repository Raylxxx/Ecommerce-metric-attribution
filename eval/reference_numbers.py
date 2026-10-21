"""计算每个用例的「标准数字」，交给裁判比对，而不是让裁判自己算。

在注入后的数据上用 attribution/lmdi.py 算 ΔGMV、三因子贡献、期望人群的变化。
另外算一个「难度」：注入带来的 GMV 变化 / 历史周同比波动。小于 2 的用例被自然波动淹没，标为 hard，
汇总准确率时我会把 hard 单独列出来。

    python eval/reference_numbers.py              # 查 BigQuery 上的 case 视图
    （离线基线在 eval/offline_baseline.py 里直接调用 compute_reference）
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from attribution.lmdi import lmdi_gmv  # noqa: E402
from attribution.metrics import row_of  # noqa: E402
from eval.inject.generate_cases import CASES_DIR, read_jsonl, write_jsonl  # noqa: E402


def wow_sd(clean_daily: pd.DataFrame, before) -> float | None:
    d = clean_daily.copy()
    d["event_dt"] = pd.to_datetime(d["event_dt"])
    d = d.sort_values("event_dt").set_index("event_dt")
    wow = (d["gmv"] / d["gmv"].shift(7) - 1)
    hist = wow[wow.index < pd.Timestamp(before)].dropna().tolist()
    return statistics.pstdev(hist) if len(hist) >= 8 else None


def compute_reference(case: dict, injected_daily: pd.DataFrame, original_daily: pd.DataFrame) -> dict:
    cur, base = case["date"], case["base_date"]
    ref = {"case_id": case["case_id"], "cur_dt": cur, "base_dt": base}
    try:
        r = lmdi_gmv(row_of(injected_daily, base), row_of(injected_daily, cur))
    except (KeyError, ValueError) as e:
        return {**ref, "error": str(e)}
    ref.update({
        "gmv0": round(r["gmv0"], 2), "gmv1": round(r["gmv1"], 2),
        "delta_gmv": round(r["delta"], 2), "pct_change": round(r["pct_change"], 4),
        "factor_contrib": {k: round(v, 2) for k, v in r["contrib"].items()},
        "factor_share": {k: round(v, 4) for k, v in r["share"].items()},
        "factor_change": {k: round(v, 4) for k, v in r["factor_change"].items()},
        "observed_top_factor": r["top_factor"],
    })
    # 注入本身带来的变化 = 注入后当前期 GMV − 注入前当前期 GMV
    g_orig = row_of(original_daily, cur)["gmv"]
    g_inj = row_of(injected_daily, cur)["gmv"]
    injected_effect = (g_inj - g_orig) / row_of(original_daily, base)["gmv"]
    sd = wow_sd(original_daily, base)
    ref["injected_effect_pct"] = round(injected_effect, 4)
    ref["natural_wow_sd"] = round(sd, 4) if sd else None
    if case["type"] in ("traffic", "conversion", "aov"):
        ratio = abs(injected_effect) / sd if sd else None
        ref["difficulty"] = "hard" if ratio is not None and ratio < 2 else "normal"
    else:
        ref["difficulty"] = "normal"
    return ref


def _bq_daily(client, project: str, dataset: str, table: str) -> pd.DataFrame:
    return client.query(f"SELECT * FROM `{project}.{dataset}.{table}` ORDER BY event_dt").to_dataframe()


def main() -> None:
    from google.cloud import bigquery

    project = os.environ["GCP_PROJECT_ID"]
    client = bigquery.Client(project=project)
    original = _bq_daily(client, project, "ga4_attr", "ads_daily_total")
    refs = []
    for case in read_jsonl(CASES_DIR / "ground_truth.jsonl"):
        inj = _bq_daily(client, project, "ga4_eval", f"{case['case_id']}_ads_daily_total")
        refs.append(compute_reference(case, inj, original))
        print(json.dumps(refs[-1], ensure_ascii=False))
    write_jsonl(refs, CASES_DIR / "reference_numbers.jsonl")


if __name__ == "__main__":
    main()

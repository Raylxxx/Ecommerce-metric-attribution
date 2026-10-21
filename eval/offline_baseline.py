"""离线规则基线：在合成数据上跑「注入 → attribution.pipeline → 结构化打分」。

它不是 AI 助手的准确率，作用有两个：
1. 不花钱、不连 BigQuery，就能检查注入逻辑、打分逻辑有没有写错（单测里也跑了一部分）；
2. 给 AI 助手一个对照：同一套四步法规则写死成代码能做到多少，AI 至少不应该比它差太多。

    python eval/offline_baseline.py              # 50 个用例，约几分钟
    python eval/offline_baseline.py --limit 10
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from attribution.metrics import clean_events, daily_total  # noqa: E402
from attribution.pipeline import run_offline  # noqa: E402
from attribution.synthetic import SyntheticConfig, generate_events  # noqa: E402
from eval.inject.generate_cases import make_cases, write_jsonl  # noqa: E402
from eval.inject.offline_inject import inject  # noqa: E402
from eval.reference_numbers import compute_reference  # noqa: E402
from eval.scoring import score_root_cause  # noqa: E402

OUT = ROOT / "eval" / "results" / "offline_baseline"
CACHE = ROOT / "data" / "synthetic" / "events_clean.pkl"


def load_synthetic(cfg: SyntheticConfig | None = None, use_cache: bool = True) -> pd.DataFrame:
    if use_cache and CACHE.exists():
        return pd.read_pickle(CACHE)
    ev, _ = clean_events(generate_events(cfg or SyntheticConfig()))
    if use_cache:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        ev.to_pickle(CACHE)
    return ev


def calm_dates(daily: pd.DataFrame, max_abs_z: float = 1.0, min_history_days: int = 35) -> list[str]:
    """和 00_find_anomalies.sql 同样的思路：周同比的 z 值小于 1 的日期。"""
    d = daily.copy()
    d["event_dt"] = pd.to_datetime(d["event_dt"])
    d = d.sort_values("event_dt").set_index("event_dt")
    wow = d["gmv"] / d["gmv"].shift(7) - 1
    z = (wow - wow.mean()) / wow.std()
    start = d.index.min() + pd.Timedelta(days=min_history_days)
    return [str(i.date()) for i, v in z.items() if i >= start and pd.notna(v) and abs(v) < max_abs_z]


def run(limit: int | None = None, events: pd.DataFrame | None = None, seed: int = 42) -> dict:
    ev = events if events is not None else load_synthetic()
    daily = daily_total(ev)
    cases = make_cases(calm_dates(daily), seed=seed)
    if limit:
        # 每种类型都取一点，保证小样本时也覆盖到
        by = {}
        for c in cases:
            by.setdefault(c["type"], []).append(c)
        cases = [c for i in range(limit) for lst in by.values() if i < len(lst) for c in [lst[i]]][:limit]
    rows = []
    for c in cases:
        t0 = time.time()
        inj = inject(ev, c)
        res = run_offline(inj, c["date"], c["base_date"])
        ref = compute_reference(c, daily_total(inj), daily)
        sc = score_root_cause(c, res["check"], res["decompose"], ref.get("difficulty"))
        rows.append({"case_id": c["case_id"], "type": c["type"], "date": c["date"],
                     "verdict": res["check"]["verdict"], "issue_type": res["check"]["issue_type"],
                     "top_factor": (res["decompose"] or {}).get("top_factor"),
                     "top_segment": ((res["decompose"] or {}).get("segment_search") or {}).get("top_segment"),
                     "expected_segment": c["segment"], "difficulty": ref.get("difficulty"),
                     "injected_effect_pct": ref.get("injected_effect_pct"),
                     "seconds": round(time.time() - t0, 2), **sc})
    return {"cases": cases, "rows": rows}


def summarize(rows: list[dict]) -> dict:
    def acc(rs):
        return round(sum(r["root_cause"] == 2 for r in rs) / len(rs), 4) if rs else None
    types = sorted({r["type"] for r in rows})
    return {
        "n": len(rows),
        "root_cause_acc": acc(rows),
        "root_cause_acc_normal_only": acc([r for r in rows if r["difficulty"] != "hard"]),
        "n_hard": sum(r["difficulty"] == "hard" for r in rows),
        "by_type": {t: acc([r for r in rows if r["type"] == t]) for t in types},
        "avg_seconds": round(statistics.mean(r["seconds"] for r in rows), 2),
        "note": "合成数据 + 确定性规则基线，不代表 AI 助手在真实数据上的表现",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    out = run(a.limit)
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(out["cases"], OUT / "cases.jsonl")
    write_jsonl(out["rows"], OUT / "runs.jsonl")
    s = summarize(out["rows"])
    (OUT / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in out["rows"]:
        print(f"{r['case_id']} {r['type']:<13} {r['verdict']:<13} 根因={r['root_cause']} {r['difficulty']:<6} {r['reason']}")
    print(json.dumps(s, ensure_ascii=False, indent=2))

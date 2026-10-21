"""生成评测用例 ground_truth.jsonl（50 个，原因已知）。

真实数据里异动的「原因」没有标准答案，所以我人为制造已知原因的异动：
在真实清洗数据上做受控扰动 → 标准答案已知 → 让助手去归因 → 打分。

| 类型          | 数量 | 正确答案 |
|---------------|------|----------|
| traffic       | 10   | UV 主导，定位到人群 |
| conversion    | 10   | CR 主导，定位到人群 + 结算环节 |
| aov           | 10   | AOV 主导，定位到人群 |
| tracking_loss | 10   | 判为埋点丢失，不给业务结论 |
| delay         | 5    | 判为数据延迟 |
| control       | 5    | 无显著异动 |

注入只在「平静」日期上做：当前期本身和上周同日差异小（|z| < 1），
否则真实波动会和注入原因混在一起，标准答案就不唯一了。
平静日期用 sql/04_attribution/00_find_anomalies.sql 的 z 值筛出来，写进 eval/cases/calm_dates.txt。

    python eval/inject/generate_cases.py                        # 读 calm_dates.txt
    python eval/inject/generate_cases.py --calm-dates 2020-12-02,2020-12-09
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "eval" / "cases"

TYPES = (["traffic"] * 10 + ["conversion"] * 10 + ["aov"] * 10
         + ["tracking_loss"] * 10 + ["delay"] * 5 + ["control"] * 5)

# 人群既有单维度也有双维度，检验下钻会不会「拆过头」或「拆不够」
SEGMENTS = [
    {"device": "mobile"},
    {"device": "desktop"},
    {"channel": "organic"},
    {"channel": "referral"},
    {"channel": "organic", "device": "desktop"},
    {"channel": "organic", "device": "mobile"},
    {"channel": "(none)", "device": "desktop"},
    {"channel": "referral", "device": "desktop"},
]
# 原计划幅度是 10%–40%。在合成数据上试跑离线基线后发现：人群只占 20%–50% 的 GMV 时，
# 这个幅度带来的整体变化大多不到 2 倍自然波动（单日订单量小，GMV 噪音大），绝大部分用例被淹没。
# 所以提高到 30%–70%；真实数据上每个用例的难度以 reference_numbers.py 的标注为准。
MAGNITUDES = [0.3, 0.5, 0.7]
TRACKING_EVENTS = ["view_item", "add_to_cart", "begin_checkout"]
TRACKING_OS = [None, "iOS", "Android"]
DELAY_HOURS = list(range(14, 22))

# 占位：真实平静日期以 00_find_anomalies.sql 实测为准
DEFAULT_CALM_DATES = ["2020-11-18", "2020-12-02", "2020-12-09", "2021-01-13"]

EXPECTED_FACTOR = {"traffic": "uv", "conversion": "cr", "aov": "aov"}
EXPECTED_SUB = {"conversion": "checkout_rate"}  # 结算及之后的事件被删，变化最大的环节应在结算附近
EXPECTED_ISSUE = {"tracking_loss": "tracking_loss", "delay": "data_delay"}


def make_case(i: int, t: str, rng: random.Random, calm_dates: list[str]) -> dict:
    dt = rng.choice(calm_dates)
    base = (date.fromisoformat(dt) - timedelta(days=7)).isoformat()
    case = {"case_id": f"case_{i:03d}", "type": t, "date": dt, "base_date": base,
            "segment": None, "magnitude": None, "params": {}}
    if t in EXPECTED_FACTOR:
        case["segment"] = rng.choice(SEGMENTS)
        case["magnitude"] = rng.choice(MAGNITUDES)
    elif t == "tracking_loss":
        case["magnitude"] = rng.choice([0.3, 0.5, 0.7])
        case["params"] = {"event": rng.choice(TRACKING_EVENTS), "os": rng.choice(TRACKING_OS)}
    elif t == "delay":
        case["params"] = {"hour": rng.choice(DELAY_HOURS)}

    is_real = t in EXPECTED_FACTOR
    case["expected"] = {
        "verdict": "real_anomaly" if is_real else ("no_anomaly" if t == "control" else "data_issue"),
        "is_real_anomaly": is_real,
        "issue_type": EXPECTED_ISSUE.get(t),
        "top_factor": EXPECTED_FACTOR.get(t),
        "top_sub_factor": EXPECTED_SUB.get(t),
        "segment": case["segment"],
    }
    case["question"] = f"GMV {dt} 和上周同日（{base}）相比有变化，原因是什么？"
    return case


def make_cases(calm_dates: list[str], seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    return [make_case(i, t, rng, calm_dates) for i, t in enumerate(TYPES, 1)]


def load_calm_dates(arg: str | None) -> list[str]:
    if arg:
        return [d.strip() for d in arg.split(",") if d.strip()]
    f = CASES_DIR / "calm_dates.txt"
    if f.exists():
        ds = [x.strip() for x in f.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]
        if ds:
            return ds
    return DEFAULT_CALM_DATES


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calm-dates")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(CASES_DIR / "ground_truth.jsonl"))
    a = ap.parse_args()
    cases = make_cases(load_calm_dates(a.calm_dates), a.seed)
    write_jsonl(cases, Path(a.out))
    print(f"已生成 {len(cases)} 个用例 → {a.out}")

"""汇总一个版本的评测结果，写进 eval/results/summary.csv（每个版本一行），并输出分类型准确率。

    python eval/summarize.py --version v1 --note "基础 Skill"
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.inject.generate_cases import CASES_DIR, read_jsonl  # noqa: E402

RESULTS = ROOT / "eval" / "results"
FIELDS = ["version", "note", "n", "root_cause_acc", "numbers_2_rate", "actionable_2_rate",
          "fake_detect_rate", "control_acc", "structured_root_cause_acc", "avg_seconds", "avg_cost_usd"]


def rate(xs) -> float | None:
    xs = [x for x in xs if x is not None]
    return round(sum(1 for x in xs if x == 2) / len(xs), 4) if xs else None


def summarize(cases: list[dict], judge: list[dict], runs: list[dict]) -> tuple[dict, list[dict]]:
    t = {c["case_id"]: c["type"] for c in cases}
    j = {r["case_id"]: r for r in judge}
    rr = {r["case_id"]: r for r in runs}
    ids = [c["case_id"] for c in cases]

    def jcol(col, only=None):
        return [j.get(i, {}).get(col) for i in ids if only is None or t[i] in only]

    row = {
        "n": len(ids),
        "root_cause_acc": rate(jcol("root_cause")),
        "numbers_2_rate": rate(jcol("numbers")),
        "actionable_2_rate": rate(jcol("actionable")),
        "fake_detect_rate": rate(jcol("root_cause", {"tracking_loss", "delay"})),
        "control_acc": rate(jcol("root_cause", {"control"})),
        "structured_root_cause_acc": rate([rr.get(i, {}).get("root_cause") for i in ids]),
        "avg_seconds": round(statistics.mean([rr[i]["seconds"] for i in ids if i in rr]), 1) if rr else None,
        "avg_cost_usd": (round(statistics.mean(c), 4)
                         if (c := [rr[i]["cost_usd"] for i in ids if rr.get(i, {}).get("cost_usd") is not None])
                         else None),
    }
    by_type = []
    for ty in sorted(set(t.values())):
        sub = [i for i in ids if t[i] == ty]
        by_type.append({"type": ty, "n": len(sub),
                        "root_cause_acc": rate([j.get(i, {}).get("root_cause") for i in sub]),
                        "structured_root_cause_acc": rate([rr.get(i, {}).get("root_cause") for i in sub])})
    return row, by_type


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    vdir = RESULTS / a.version
    cases = read_jsonl(CASES_DIR / "ground_truth.jsonl")
    judge = read_jsonl(vdir / "judge_scores.jsonl") if (vdir / "judge_scores.jsonl").exists() else []
    runs = read_jsonl(vdir / "runs.jsonl") if (vdir / "runs.jsonl").exists() else []
    row, by_type = summarize(cases, judge, runs)
    row = {"version": a.version, "note": a.note, **row}

    path = RESULTS / "summary.csv"
    old = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            old = [r for r in csv.DictReader(f) if r["version"] != a.version]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(old + [row])
    with open(vdir / "by_type.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["type", "n", "root_cause_acc", "structured_root_cause_acc"])
        w.writeheader()
        w.writerows(by_type)
    print(row)
    for b in by_type:
        print(b)


if __name__ == "__main__":
    main()

"""裁判 vs 人工的一致性：完全一致率 + 根因维度的 Cohen's Kappa。

做法：分层抽 20 条（每种类型都有），我先不看裁判分数，按同一份 rubric 盲打分，
填进 eval/human_check.csv，然后跑这个脚本。Kappa ≥ 0.7 认为裁判可信；
不达标就改裁判提示词（加打分示例），重新抽检。

    python eval/agreement.py --version v1
    python eval/agreement.py --version v1 --sample 20     # 生成待打分的抽样清单
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.inject.generate_cases import CASES_DIR, read_jsonl  # noqa: E402

HUMAN = ROOT / "eval" / "human_check.csv"
DIMS = ("root_cause", "numbers", "actionable")


def cohen_kappa(a: list, b: list) -> float:
    """两位评分者在同一组样本上的 Cohen's Kappa（不依赖 sklearn）。"""
    if len(a) != len(b) or not a:
        raise ValueError("两组评分长度必须相同且非空")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if pe == 1:
        return 1.0
    return (po - pe) / (1 - pe)


def stratified_sample(cases: list[dict], k: int = 20, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    by_type: dict[str, list[str]] = {}
    for c in cases:
        by_type.setdefault(c["type"], []).append(c["case_id"])
    picked = []
    types = sorted(by_type)
    while len(picked) < k and any(by_type.values()):
        for ty in types:
            if by_type[ty] and len(picked) < k:
                picked.append(by_type[ty].pop(rng.randrange(len(by_type[ty]))))
    return sorted(picked)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--sample", type=int)
    a = ap.parse_args()
    cases = read_jsonl(CASES_DIR / "ground_truth.jsonl")

    if a.sample:
        ids = stratified_sample(cases, a.sample)
        with open(HUMAN, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["case_id", "type", *(f"human_{d}" for d in DIMS), "note"])
            t = {c["case_id"]: c["type"] for c in cases}
            for i in ids:
                w.writerow([i, t[i], "", "", "", ""])
        print(f"已生成抽样清单 {HUMAN}，请打开 eval/results/{a.version}/<case_id>/report.md 盲打分")
        return

    judge = {r["case_id"]: r for r in read_jsonl(ROOT / "eval" / "results" / a.version / "judge_scores.jsonl")}
    with open(HUMAN, encoding="utf-8") as f:
        human = [r for r in csv.DictReader(f) if r["human_root_cause"] != ""]
    if not human:
        print("human_check.csv 还没有打分")
        return
    pairs = [(r, judge[r["case_id"]]) for r in human if judge.get(r["case_id"], {}).get("root_cause") is not None]
    exact = sum(all(int(h[f"human_{d}"]) == j[d] for d in DIMS) for h, j in pairs) / len(pairs)
    k = cohen_kappa([int(h["human_root_cause"]) for h, _ in pairs], [j["root_cause"] for _, j in pairs])
    print(f"样本数 {len(pairs)}，三项完全一致率 {exact:.0%}，根因维度 Kappa = {k:.3f}"
          f"（{'可信' if k >= 0.7 else '不达标，需要改裁判提示词'}）")


if __name__ == "__main__":
    main()

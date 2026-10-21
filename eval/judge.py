"""LLM-as-a-Judge：按 rubric.md 给助手生成的报告打分。

- 裁判拿到的是标准答案 + Python 算好的参考数字，只做比对；
- 裁判和被测助手用不同的提示词，模型可以通过 JUDGE_MODEL 换成不同的模型，减少「自己给自己打高分」；
- 输出解析失败会重试，仍失败就记为 None，汇总时单独统计。

    python eval/judge.py --version v1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.inject.generate_cases import CASES_DIR, read_jsonl, write_jsonl  # noqa: E402

MODEL = os.environ.get("JUDGE_MODEL", "claude-sonnet-5-5")
RUBRIC = (ROOT / "eval" / "rubric.md").read_text(encoding="utf-8")
RESULTS = ROOT / "eval" / "results"

PROMPT = """你是严格的数据分析评审。按评分标准给一份「指标异动归因报告」打分。

<rubric>
{rubric}
</rubric>

<ground_truth>
{truth}
</ground_truth>

<reference_numbers>
{ref}
</reference_numbers>

<report>
{report}
</report>

先在心里逐条对照，再只输出一个 JSON，不要输出其他内容：
{{"root_cause": 0-2, "numbers": 0-2, "actionable": 0-2, "reason": "一句话说明扣分点"}}"""


def parse_scores(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    for k in ("root_cause", "numbers", "actionable"):
        if d.get(k) not in (0, 1, 2):
            return None
    return d


def judge_one(client, case: dict, report: str, ref: dict, retries: int = 2) -> dict:
    truth = {k: case[k] for k in ("case_id", "type", "date", "base_date", "segment", "magnitude", "params", "expected")}
    prompt = PROMPT.format(rubric=RUBRIC, truth=json.dumps(truth, ensure_ascii=False),
                           ref=json.dumps(ref, ensure_ascii=False), report=report)
    for i in range(retries + 1):
        msg = client.messages.create(model=MODEL, max_tokens=1024,
                                     messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        d = parse_scores(text)
        if d:
            return d
        time.sleep(2 * (i + 1))
    return {"root_cause": None, "numbers": None, "actionable": None, "reason": "裁判输出解析失败"}


def main() -> None:
    import anthropic

    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    a = ap.parse_args()

    client = anthropic.Anthropic()
    cases = {c["case_id"]: c for c in read_jsonl(CASES_DIR / "ground_truth.jsonl")}
    ref_path = CASES_DIR / "reference_numbers.jsonl"
    refs = {r["case_id"]: r for r in read_jsonl(ref_path)} if ref_path.exists() else {}
    out = []
    for cid, case in cases.items():
        rpt = RESULTS / a.version / cid / "report.md"
        if not rpt.exists():
            out.append({"case_id": cid, "root_cause": 0, "numbers": 0, "actionable": 0, "reason": "没有生成报告"})
            continue
        s = judge_one(client, case, rpt.read_text(encoding="utf-8"), refs.get(cid, {}))
        out.append({"case_id": cid, **s})
        print(cid, s)
    write_jsonl(out, RESULTS / a.version / "judge_scores.jsonl")


if __name__ == "__main__":
    main()

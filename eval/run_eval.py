"""批量运行 AI 归因助手（Claude Code 无交互模式）。

每个用例：
1. 设置 BQ_DATASET=ga4_eval、BQ_TABLE_PREFIX=case_xxx_，MCP 服务器随 claude 进程启动，自动查到该用例的视图；
2. `claude -p` 跑一遍，输出写到 eval/results/<version>/<case_id>/；
3. 记录耗时（「单次排查耗时」的实测来源）和花费；
4. 用 eval/scoring.py 对落盘的 JSON 做结构化打分。

    python eval/run_eval.py --version v1 --note "基础 Skill"
    python eval/run_eval.py --version v1 --only case_001,case_031    # 先跑几个调试
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.inject.generate_cases import CASES_DIR, read_jsonl, write_jsonl  # noqa: E402
from eval.scoring import score_root_cause  # noqa: E402

RESULTS = ROOT / "eval" / "results"


def build_prompt(case: dict, out_dir: Path) -> str:
    rel = out_dir.relative_to(ROOT).as_posix()
    return (f"{case['question']}\n"
            f"本次数据集是 ga4_eval，表名前缀 {case['case_id']}_（以 describe_tables 返回为准）。"
            f"当前期 {case['date']}，基准期 {case['base_date']}。"
            f"所有中间结果和报告写到 {rel}/ 目录，报告文件名 report.md。")


def _load_json(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def run_case(case: dict, version: str, timeout: int, difficulty: str | None = None) -> dict:
    out_dir = RESULTS / version / case["case_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "BQ_DATASET": "ga4_eval", "BQ_TABLE_PREFIX": f"{case['case_id']}_"}
    cmd = ["claude", "-p", build_prompt(case, out_dir), "--output-format", "json"]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env,
                           cwd=ROOT, encoding="utf-8")
        stdout, status = r.stdout, ("ok" if r.returncode == 0 else f"exit {r.returncode}")
    except subprocess.TimeoutExpired:
        stdout, status = "", "timeout"
    seconds = round(time.time() - t0, 1)
    (out_dir / "raw.json").write_text(stdout or "", encoding="utf-8")

    meta = _load_json(out_dir / "raw.json") or {}
    check, dec = _load_json(out_dir / "01_check.json"), _load_json(out_dir / "02_decompose.json")
    return {"case_id": case["case_id"], "type": case["type"], "status": status, "seconds": seconds,
            "cost_usd": meta.get("total_cost_usd"), "num_turns": meta.get("num_turns"),
            "has_report": (out_dir / "report.md").exists(), "difficulty": difficulty,
            **score_root_cause(case, check, dec, difficulty)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="版本号，例如 v1")
    ap.add_argument("--note", default="", help="这一版改了什么（每一版只改一处）")
    ap.add_argument("--only", help="逗号分隔的 case_id")
    ap.add_argument("--timeout", type=int, default=1200)
    a = ap.parse_args()

    cases = read_jsonl(CASES_DIR / "ground_truth.jsonl")
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c["case_id"] in keep]
    ref_path = CASES_DIR / "reference_numbers.jsonl"
    diff = {r["case_id"]: r.get("difficulty") for r in read_jsonl(ref_path)} if ref_path.exists() else {}
    rows = []
    for c in cases:
        r = run_case(c, a.version, a.timeout, diff.get(c["case_id"]))
        rows.append(r)
        print(f"{r['case_id']} {r['type']:<13} {r['status']:<8} {r['seconds']:>6}s 根因={r['root_cause']} {r['reason']}")
    write_jsonl(rows, RESULTS / a.version / "runs.jsonl")
    (RESULTS / a.version / "NOTE.md").write_text(f"# {a.version}\n\n改动：{a.note}\n", encoding="utf-8")
    print(f"完成 {len(rows)} 个用例，接下来：python eval/judge.py --version {a.version} && "
          f"python eval/summarize.py --version {a.version}")


if __name__ == "__main__":
    main()

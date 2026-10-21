"""离线演示：合成数据 + 注入一个「自然流量转化下降」→ 跑完四步 → 输出到 examples/demo_run/。

没有 GCP 账号也能看到完整产出长什么样：01_check.json、02_decompose.json、report.md。
注意这里的数字来自合成数据，只用来展示流程和格式。

    python scripts/demo_offline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attribution.metrics import clean_events  # noqa: E402
from attribution.pipeline import run_offline  # noqa: E402
from attribution.report import render_report  # noqa: E402
from attribution.synthetic import SyntheticConfig, generate_events  # noqa: E402
from eval.inject.offline_inject import inject  # noqa: E402

OUT = ROOT / "examples" / "demo_run"
CASE = {"case_id": "demo", "type": "conversion", "date": "2020-12-15", "base_date": "2020-12-08",
        "segment": {"channel": "organic"}, "magnitude": 0.7, "params": {}}


def main() -> None:
    raw = generate_events(SyntheticConfig(start="2020-11-01", end="2020-12-20"))
    events, clean_stats = clean_events(raw)
    res = run_offline(inject(events, CASE), CASE["date"], CASE["base_date"])
    OUT.mkdir(parents=True, exist_ok=True)
    dump = lambda o: json.dumps(o, ensure_ascii=False, indent=2, default=str)  # noqa: E731
    (OUT / "00_case.json").write_text(dump({"injected": CASE, "clean_stats": clean_stats}), encoding="utf-8")
    (OUT / "01_check.json").write_text(dump(res["check"]), encoding="utf-8")
    if res["decompose"]:
        (OUT / "02_decompose.json").write_text(dump(res["decompose"]), encoding="utf-8")
    note = ("离线演示：数据为 attribution/synthetic.py 生成的合成数据，并人为注入了"
            "「organic 渠道 70% 买家结算后流失」。数字只用于展示流程，不是 Google Merchandise Store 的真实结论。")
    (OUT / "report.md").write_text(render_report(res, source_note=note), encoding="utf-8")
    print(f"已输出到 {OUT}，判定：{res['check']['verdict']}，"
          f"主导因子：{(res['decompose'] or {}).get('top_factor')}")


if __name__ == "__main__":
    main()

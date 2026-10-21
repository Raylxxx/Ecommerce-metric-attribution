import json

from attribution.pipeline import run_offline
from attribution.report import render_report
from eval.inject.offline_inject import inject


def test_pipeline_outputs_are_json_serializable_and_reported(events):
    case = {"case_id": "rep", "type": "conversion", "date": "2020-12-09",
            "segment": {"channel": "organic"}, "magnitude": 0.6, "params": {}}
    res = run_offline(inject(events, case), "2020-12-09", "2020-12-02")
    json.dumps(res, ensure_ascii=False, default=str)
    md = render_report(res)
    assert md.startswith("# ")
    assert "## 2. 是否为真异动" in md and "## 6. 局限" in md
    if res["decompose"]:
        assert abs(res["decompose"]["lmdi_residual"]) < 1e-6
        assert "## 3. 因子拆解" in md


def test_report_for_data_issue(events):
    case = {"case_id": "rep2", "type": "delay", "date": "2020-12-09", "params": {"hour": 16}}
    res = run_offline(inject(events, case), "2020-12-09")
    md = render_report(res)
    assert res["check"]["verdict"] == "data_issue"
    assert "数据延迟" in md and "## 3. 因子拆解" not in md

"""结构化打分：直接比对助手落盘的 01_check.json / 02_decompose.json 和标准答案。

LLM 裁判看的是报告全文（数字对不对、建议能不能落地），这里只管「根因」这一项，
规则是确定的、可复现的。两者一起看：裁判分和结构化分差很多的用例，我会人工复核。
离线规则基线也用这个函数打分。
"""

from __future__ import annotations


def segment_match(expected: dict | None, predicted: dict | None) -> float:
    """1.0 = 完全命中（预测人群包含期望人群的全部条件）；0.5 = 部分命中；0 = 不对。"""
    if not expected:
        return 1.0
    if not predicted:
        return 0.0
    exp, pred = set(expected.items()), set(predicted.items())
    if exp <= pred and len(pred) - len(exp) <= 1:
        return 1.0 if pred == exp else 0.5   # 多拆了一层（比如又加了 country）算部分命中
    if pred <= exp or exp & pred:
        return 0.5
    return 0.0


def score_root_cause(case: dict, check: dict | None, decompose: dict | None,
                     difficulty: str | None = None) -> dict:
    """按 eval/rubric.md 的「根因准确」维度打 0/1/2 分。

    difficulty == "hard"（注入效应 < 2 倍自然波动）时，回答「无显著异动」记 1 分：
    这种情况下说不显著在统计上是站得住的，不能算完全答错。
    """
    exp = case["expected"]
    if not check:
        return {"root_cause": 0, "reason": "没有 01_check.json"}
    verdict = check.get("verdict")

    if exp["verdict"] == "data_issue":
        if verdict != "data_issue":
            return {"root_cause": 0, "reason": f"应判为数据问题，实际 {verdict}"}
        if check.get("issue_type") == exp["issue_type"]:
            return {"root_cause": 2, "reason": "数据问题类型正确"}
        return {"root_cause": 1, "reason": f"判为数据问题，但类型 {check.get('issue_type')} ≠ {exp['issue_type']}"}

    if exp["verdict"] == "no_anomaly":
        ok = verdict == "no_anomaly"
        return {"root_cause": 2 if ok else 0, "reason": "正确判为无显著异动" if ok else f"对照组被判为 {verdict}"}

    # 真异动
    if verdict == "no_anomaly" and difficulty == "hard":
        return {"root_cause": 1, "reason": "hard 用例被判为无显著异动（注入效应被自然波动淹没）"}
    if verdict != "real_anomaly" or not decompose:
        return {"root_cause": 0, "reason": f"真异动被判为 {verdict}"}
    factor_ok = decompose.get("top_factor") == exp["top_factor"]
    segs = decompose.get("top_segments") or []
    top_seg = segs[0]["segment"] if segs else None
    m = segment_match(exp["segment"], top_seg)
    # Top1 没命中、但 Top3 里有期望人群，也算部分命中
    if m < 1 and any(segment_match(exp["segment"], s.get("segment")) == 1.0 for s in segs[:3]):
        m = max(m, 0.5)
    if factor_ok and m == 1.0:
        return {"root_cause": 2, "reason": "主导因子和人群都正确"}
    if factor_ok or m == 1.0:
        return {"root_cause": 1, "reason": f"因子{'正确' if factor_ok else '错误'}，人群匹配度 {m}"}
    return {"root_cause": 0, "reason": f"因子 {decompose.get('top_factor')}≠{exp['top_factor']}，人群 {top_seg}"}

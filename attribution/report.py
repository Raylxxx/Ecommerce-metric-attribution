"""把 01_check.json / 02_decompose.json 渲染成 Markdown 报告。

格式和 .claude/skills/metric-attribution/report_template.md 一致。
线上由 report-writer 这个 subagent 写报告；这里的渲染器用于离线规则基线和样例输出，
同时也是我给 report-writer 定格式时的参照。
"""

from __future__ import annotations

FACTOR_CN = {"uv": "访客数 UV", "cr": "下单转化率 CR", "aov": "客单价 AOV"}
SUB_CN = {
    "view_rate": "商品浏览率", "cart_rate": "加购率", "checkout_rate": "结算率",
    "completion_rate": "下单完成率", "orders_per_buyer": "人均订单数",
    "items_per_order": "每单件数", "avg_item_price": "件单价",
}
ISSUE_CN = {"tracking_loss": "疑似埋点丢失", "data_delay": "疑似数据延迟/截断",
            "definition_change": "疑似口径/埋点变更"}


def _money(v: float) -> str:
    return f"{'+' if v >= 0 else '-'}${abs(v):,.0f}"


def _seg(seg: dict) -> str:
    return " × ".join(f"{k}={v}" for k, v in seg.items())


def _fmt_factor(f: str, v: float) -> str:
    if f == "uv":
        return f"{v:,.0f}"
    if f == "cr":
        return f"{v:.2%}"
    return f"${v:,.2f}"


def _fmt_change(f: str, v: float) -> str:
    return f"{v:+.2f}pp" if f == "cr" else f"{v:+.1%}"


def render_report(result: dict, title: str | None = None, source_note: str | None = None) -> str:
    check, dec = result["check"], result.get("decompose")
    cur, base = check["cur_dt"], check["base_dt"]
    title = title or f"GMV 异动归因：{cur} vs {base}"
    L = [f"# {title}", ""]
    if source_note:
        L += [f"> {source_note}", ""]

    # ---- TL;DR
    L += ["## TL;DR", ""]
    sig = check["significance"]
    if check["verdict"] == "data_issue":
        L += [f"- 结论：**{ISSUE_CN.get(check['issue_type'], '数据问题')}**，不是业务异动，暂不做业务归因。[E1]",
              f"- 表面变化：GMV {sig['pct_change']:+.1%}（{cur} vs {base}）。[E2]",
              "- 建议：先通知数据/埋点负责人排查，修复后重新跑本流程。"]
    elif check["verdict"] == "no_anomaly":
        L += [f"- 结论：**无显著异动**，GMV {sig['pct_change']:+.1%} 在历史正常波动范围内。[E2]",
              "- 不建议据此调整业务动作，继续按日监控即可。", ""]
    else:
        top = dec["top_factor"]
        share = dec["factor_share"][top]
        seg = dec["segment_search"]
        seg_txt = _seg(seg["top_segment"]) if seg["top_segment"] else "未定位到集中人群"
        L += [f"- GMV {dec['pct_change']:+.1%}（{_money(dec['delta_gmv'])}），{cur} vs {base}。[E3]",
              f"- 主要原因：{FACTOR_CN[top]}，贡献 {share:.0%} 的变化。[E3]",
              f"- 问题集中在：{seg_txt}（占该因子变化 {seg['top_segment_share']:.0%}）。[E4]"]
    L.append("")

    # ---- 对比口径
    L += ["## 1. 背景与对比口径", "",
          f"- 当前期：{cur}；基准期：{base}（默认上周同一天）",
          "- 指标口径：docs/metrics/gmv.md、uv.md、conversion_rate.md、aov.md", ""]

    # ---- 排假
    L += ["## 2. 是否为真异动 [E1]", "", "| 检查 | 结论 |", "|---|---|"]
    for e in check["evidence"]:
        mark = "⚠️ " if e.get("flag") else ""
        L.append(f"| {e['check']} | {mark}{e['finding']} |")
    L += [f"| significance [E2] | {sig['finding']} |", "",
          f"**判定：{check['verdict']}**（置信度 {check['confidence']}）", ""]

    if dec:
        # ---- LMDI
        L += ["## 3. 因子拆解（LMDI）[E3]", "",
              "| 因子 | 基准期 | 当前期 | 变化 | 对 GMV 贡献 | 贡献占比 |", "|---|---|---|---|---|---|"]
        for f in ("uv", "cr", "aov"):
            L.append(f"| {FACTOR_CN[f]} | {_fmt_factor(f, dec['factors0'][f])} | {_fmt_factor(f, dec['factors1'][f])} | "
                     f"{_fmt_change(f, dec['factor_change'][f])} | {_money(dec['factor_contrib'][f])} | "
                     f"{dec['factor_share'][f]:.0%} |")
        L += [f"| 合计 | ${dec['gmv0']:,.0f} | ${dec['gmv1']:,.0f} | {dec['pct_change']:+.1%} | "
              f"{_money(dec['delta_gmv'])} | 100% |", "",
              f"LMDI 残差：{dec['lmdi_residual']:.2e}（三项贡献之和与 ΔGMV 一致）", ""]
        sub = dec.get("sub_decompose")
        if sub:
            L += [f"### 3.1 {FACTOR_CN[sub['parent']]} 再往下拆", "",
                  "| 子因子 | 基准期 | 当前期 | 对 GMV 贡献 | 占父因子 |", "|---|---|---|---|---|"]
            for k in sub["contrib"]:
                L.append(f"| {SUB_CN[k]} | {sub['sub0'][k]:.4f} | {sub['sub1'][k]:.4f} | "
                         f"{_money(sub['contrib'][k])} | {sub['share_of_parent'][k]:.0%} |")
            L += ["", f"变化最大的环节：**{SUB_CN[sub['top_sub_factor']]}**", ""]

        # ---- 下钻
        seg = dec["segment_search"]
        L += [f"## 4. 维度下钻（{FACTOR_CN[seg['factor']]}）[E4]", "",
              f"搜索路径：" + " → ".join("×".join(lv["chosen_dims"]) for lv in seg["levels"]), "",
              "| 人群 | 贡献占比 | 明细 |", "|---|---|---|"]
        for r in seg["top_segments"]:
            if "rate_effect" in r:
                detail = (f"转化效应 {r['rate_effect']:+.5f} / 结构效应 {r['mix_effect']:+.5f}；"
                          f"比率 {r['r0']:.4f} → {r['r1']:.4f}")
            else:
                detail = f"{r['v0']:,.0f} → {r['v1']:,.0f}（{r['delta']:+,.0f}）"
            L.append(f"| {_seg(r['segment'])} | {r['share_of_change']:.0%} | {detail} |")
        L.append("")

        # ---- 建议
        top = dec["top_factor"]
        s = seg["top_segment"]
        sub_txt = SUB_CN[dec["sub_decompose"]["top_sub_factor"]] if dec.get("sub_decompose") else FACTOR_CN[top]
        target = _seg(s) if s else "全站"
        L += ["## 5. 结论与建议", "", "| 发现 | 建议 | 负责方 | 验证指标 / 恢复标准 |", "|---|---|---|---|",
              f"| {target} 的{sub_txt}变化是主因 | 排查 {cur} 前后该人群相关的页面改版、投放或活动变更 | "
              f"产品 / 投放 | 按天监控该人群{sub_txt}，回到基准期水平视为修复 |", ""]

    L += ["## 6. 局限", "",
          "- 渠道为用户首次获客媒介（traffic_source.medium），不是本次会话渠道；",
          "- 分维度 UV 不严格可加，UV 下钻占比为近似值；",
          "- 单日对比受随机波动影响，结论需结合连续多日趋势确认。", ""]
    L += ["## 附录：证据编号", "",
          "- E1：sql/04_attribution/01_event_mix.sql、02_hourly_distribution.sql、03_new_dim_values.sql",
          "- E2：sql/04_attribution/00_find_anomalies.sql（周同比显著性）",
          "- E3：sql/04_attribution/04_lmdi.sql",
          "- E4：sql/04_attribution/05_drilldown_gmv.sql、06_drilldown_ratio.sql", ""]
    return "\n".join(L)

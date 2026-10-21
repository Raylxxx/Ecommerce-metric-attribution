"""电商指标异动归因工具库。

我把「异动归因四步法」里需要计算的部分都放在这个包里：
- metrics:       用 pandas 复刻 sql/03_ads 的指标口径（离线验证、评测算标准答案都靠它）
- anomaly_check: 第 1 步，排除假异动（埋点丢失 / 数据延迟 / 维度新值）
- lmdi:          第 2 步，LMDI 因子拆解（UV × CR × AOV，以及往下一层拆）
- drilldown:     第 3 步，维度下钻（可加指标直接分 + 比率指标拆结构/转化效应）
- pipeline:      把四步串起来，输出结构化结果
- report:        把结构化结果渲染成 Markdown 报告
- synthetic:     生成和 GA4 字段一致的合成数据，没有 BigQuery 也能跑通全流程
"""

from attribution.lmdi import log_mean, lmdi, lmdi_gmv, decompose_cr, decompose_aov
from attribution.drilldown import (
    additive_drilldown,
    ratio_drilldown,
    cr_drilldown,
    aov_drilldown,
    search_segments,
    is_concentrated,
)

__all__ = [
    "log_mean",
    "lmdi",
    "lmdi_gmv",
    "decompose_cr",
    "decompose_aov",
    "additive_drilldown",
    "ratio_drilldown",
    "cr_drilldown",
    "aov_drilldown",
    "search_segments",
    "is_concentrated",
]

__version__ = "0.1.0"

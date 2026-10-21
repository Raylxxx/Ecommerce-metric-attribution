"""SQL 模板渲染：sql/ 下的文件用 ${PROJECT}、${DATASET} 占位，跑之前替换成自己的项目。"""

from __future__ import annotations

import os
import string
from pathlib import Path


def render(path: str | Path, project: str | None = None, dataset: str | None = None) -> str:
    text = Path(path).read_text(encoding="utf-8")
    return string.Template(text).safe_substitute(
        PROJECT=project or os.environ.get("GCP_PROJECT_ID", "ecom-attribution"),
        DATASET=dataset or os.environ.get("BQ_DATASET", "ga4_attr"),
    )

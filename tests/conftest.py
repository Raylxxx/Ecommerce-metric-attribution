import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attribution.metrics import clean_events  # noqa: E402
from attribution.synthetic import SyntheticConfig, generate_events  # noqa: E402


@pytest.fixture(scope="session")
def raw_events():
    # 规模调小，整套测试几十秒内跑完；45 天保证显著性检查有足够的历史周同比
    return generate_events(SyntheticConfig(start="2020-11-01", end="2020-12-15", users_per_day=3000, seed=7))


@pytest.fixture(scope="session")
def events(raw_events):
    return clean_events(raw_events)[0]

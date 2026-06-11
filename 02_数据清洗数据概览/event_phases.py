from __future__ import annotations
# -*- coding: utf-8 -*-
"""事件叙事五阶段 · 固定日期边界（爆发期 = 2026-03-28 ~ 2026-04-05）。"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


# (中文名, 英文名, date_start, date_end)；date_end=None 表示至数据末
EVENT_PHASE_WINDOWS: list[tuple[str, str, str, str | None]] = [
    ("酝酿期", "Emergence", "2025-06-07", "2026-03-27"),
    ("爆发期", "Outbreak", "2026-03-28", "2026-04-05"),
    ("扩散期", "Diffusion", "2026-04-06", "2026-04-30"),
    ("回落期", "Cooldown", "2026-05-01", "2026-05-31"),
    ("长尾期", "Tail", "2026-06-01", None),
]

OUTBREAK_START = "2026-03-28"
OUTBREAK_END = "2026-04-05"

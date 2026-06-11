from __future__ import annotations
# -*- coding: utf-8 -*-
"""BERTopic 主报告 topic_id（屏2 展示顺序 0–5）。"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import pandas as pd

# 异化话语 = topic 4 ∪ 5
ALIEN_TOPIC_IDS = frozenset({4, 5})
ALIEN_TOPIC_PERSONAL_ATTACK = 4
ALIEN_TOPIC_PERSONA = 5

# 旧版数据 topic_id 6/7 → 4/5
LEGACY_TOPIC_ID_MAP = {6: 4, 7: 5}

ALIEN_DISPLAY = "4/5"
ALIEN_DISPLAY_LABEL = f"topic {ALIEN_DISPLAY}"


def normalize_topic_id(topic_id: int) -> int:
    tid = int(topic_id)
    return LEGACY_TOPIC_ID_MAP.get(tid, tid)


def normalize_topic_series(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    return s.map(lambda x: LEGACY_TOPIC_ID_MAP.get(int(x), int(x)) if pd.notna(x) else x)


def display_topic_id(topic_id: int) -> int:
    return normalize_topic_id(topic_id)


def is_alien_topic(topic_id: int) -> bool:
    return normalize_topic_id(topic_id) in ALIEN_TOPIC_IDS


def alien_topic_mask(series: pd.Series) -> pd.Series:
    return normalize_topic_series(series).isin(ALIEN_TOPIC_IDS)


def y_alien_series(topic_series: pd.Series) -> pd.Series:
    return alien_topic_mask(topic_series).astype(int)

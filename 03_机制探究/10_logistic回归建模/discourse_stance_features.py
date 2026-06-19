from __future__ import annotations
# -*- coding: utf-8 -*-
"""言论立场光谱（并入主体层）：互斥分类，供 699 Logistic 复用。"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import re

import pandas as pd

# 展示名 → 列名
STANCE_TYPES = [
    "道德审判官",
    "版权原教旨主义者",
    "Z世代/乐子人",
    "摇摆型/路人/和事佬",
]

STANCE_REFERENCE = "摇摆型/路人/和事佬"

RE_MORAL = re.compile(
    r"道德审判|绿茶|心机|德不配位|伪君子|没教养|飘了|装无辜|人品|下作|"
    r"网暴|辱骂|贱|滚|恶心|下头|又当又立|资本推手|黑红|"
    r"没素质|卑劣|Responsible|人设崩塌",
    re.I,
)
RE_COPYRIGHT = re.compile(
    r"版权|授权|举证|依法|侵权|原唱|原版|合法|底线|原教旨|"
    r"著作权|署名|维权|赔偿|下架|合规|知识产权|先斩后奏|"
    r"知错还|明知故犯|偷歌|抄歌",
    re.I,
)
RE_FUN = re.compile(
    r"乐子|看戏|吃瓜|整活|玩梗|笑死|又如何又能怎|又能怎|如何呢|"
    r"当笑话|图一乐|娱乐大众|精神状态|魔性|上头",
    re.I,
)
RE_SWING = re.compile(
    r"路人|和事佬|不站队|双方|都有问题|就事论事|理性|冷静|"
    r"各打五十大板|不偏|中立|理智分析|都有不对|别吵",
    re.I,
)


def classify_stance(text: str, topic_id: int = -1) -> str:
    """互斥优先级：道德审判 > 版权原教旨 > Z世代/乐子人 > 摇摆/路人（默认）。

    注意：不用异化 topic（4/5）判定立场，避免与因变量循环。
    """
    s = str(text or "")
    tid = int(topic_id)

    if RE_MORAL.search(s):
        return "道德审判官"
    if tid in (1, 3) or RE_COPYRIGHT.search(s):
        return "版权原教旨主义者"
    if RE_FUN.search(s):
        return "Z世代/乐子人"
    if RE_SWING.search(s):
        return "摇摆型/路人/和事佬"
    return "摇摆型/路人/和事佬"


def stance_col(name: str) -> str:
    mapping = {
        "道德审判官": "stance_moral",
        "版权原教旨主义者": "stance_copyright",
        "Z世代/乐子人": "stance_genz_fun",
        "摇摆型/路人/和事佬": "stance_swing",
    }
    return mapping[name]


def stance_feature_cols() -> list[str]:
    """入模 dummy（参照组：摇摆型/路人/和事佬）。"""
    return [
        "stance_moral",
        "stance_copyright",
        "stance_genz_fun",
    ]


def stance_display(col: str) -> str:
    return {
        "stance_moral": "道德审判官",
        "stance_copyright": "版权原教旨主义者",
        "stance_genz_fun": "Z世代/乐子人",
    }.get(col, col)


def add_stance_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["stance_type"] = [
        classify_stance(t, tid)
        for t, tid in zip(out["content"], out.get("topic_id", -1))
    ]
    for st in STANCE_TYPES:
        out[stance_col(st)] = (out["stance_type"] == st).astype(float)
    return out

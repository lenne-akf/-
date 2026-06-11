from __future__ import annotations
# -*- coding: utf-8 -*-
"""话语标签规则与攻击维度 · 供 page14 可视化与 Logistic 特征复用。"""
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import re

import pandas as pd

# (展示名, 正则, 默认攻击类型)
DISCOURSE_LABELS: list[tuple[str, str, str]] = [
    ("抄袭", r"抄袭|抄歌|偷歌|侵权|盗用", "言论/观点攻击"),
    ("难听", r"难听|毁歌|难[听闻]|唱得.*差|魔改", "业务能力攻击"),
    ("又当又立", r"又当又立|双标|甩锅|两面", "言论/观点攻击"),
    ("资本推手", r"资本|水军|营销号|买热搜|公关|幕后|推手", "立场/阵营攻击"),
    ("蹭热度", r"蹭热度|蹭.*热|带节奏|占用.*资源", "立场/阵营攻击"),
    ("洗白", r"洗白|狡辩|小作文|诡辩|硬洗", "言论/观点攻击"),
    ("飘了", r"飘了|太狂|狂妄|嚣张|目中无人", "人品攻击"),
    ("明知故犯", r"明知故犯|知错还|故意.*(抄|唱)", "言论/观点攻击"),
    ("绿茶", r"绿茶[婊表妹]?|🍵|绿茶行为|绿茶精", "人品攻击"),
    ("心机女", r"心机女|心机|不安好心|不单纯|有心机", "人品攻击"),
    ("德不配位", r"德不配位|才不配位|位不配德", "业务能力攻击"),
    ("资源咖", r"资源咖|靠资源|抬咖|升咖|小咖|什么咖位|咖位", "业务能力攻击"),
    ("伪君子", r"伪君子|小人|卑劣|下作|Responsible", "人品攻击"),
    ("装无辜", r"装无辜|装单纯|装可怜|装模作样|人设", "人品攻击"),
    ("没教养", r"没教养|没素质|缺乏教养", "人品攻击"),
    ("没实力", r"没实力|没作品|不配当|能力不行", "业务能力攻击"),
    ("黑红", r"黑红|名声大噪|搞塌", "立场/阵营攻击"),
    ("又如何呢", r"又如何呢|又能怎", "言论/观点攻击"),
]

SHAPLEY_LABEL_NAMES = [
    "绿茶", "心机女", "资源咖", "又当又立", "德不配位",
    "难听", "抄袭", "洗白", "飘了", "装无辜",
]

ATTACK_TYPES = [
    "人品攻击",
    "业务能力攻击",
    "言论/观点攻击",
    "立场/阵营攻击",
]

DIMENSION_PALETTE = {
    "人品攻击": "#B03A3A",
    "业务能力攻击": "#4A6FA5",
    "言论/观点攻击": "#D68910",
    "立场/阵营攻击": "#7D6608",
    "其他/综合": "#95A5A6",
}

_RE_DEFEND_OR_CONDEMN = re.compile(
    r"单依纯.*(已经|早已).*(道歉|担责|回应|处理)|"
    r"(不应|不要|别|停止|请勿|反对|不允许|不容|恳请).*(人身攻击|网暴|辱骂|造谣|上升|曲解)|"
    r"(人身攻击|网暴|辱骂|造谣).*(单依纯|单依纯本人).*(停止|可以停|过分|没必要)|"
    r"停止.*对单|别.*对单|不要.*对单|请勿.*单依纯|"
    r"不应该被|不应被|不要被.*(曲解|侮辱|造谣|攻击)|"
    r"回归.*版权|回归.*事件|理性看待|就事论事|"
    r"支持.*维权.*单|单依纯.*支持.*维权|"
    r"知错就改|立正挨打|有错认错|"
    r"心疼单依纯|说出心声",
    re.I,
)

_DIM_PATTERNS: list[tuple[str, str]] = [
    ("人品攻击", r"绿茶|心机|伪君子|装无辜|没教养|飘了|人品|下作|Responsible|又当又立"),
    ("业务能力攻击", r"难听|毁歌|没实力|德不配位|资源咖|唱得|魔改|咖位|不配当"),
    ("言论/观点攻击", r"抄袭|洗白|狡辩|小作文|明知故犯|又如何|又能怎|甩锅|双标"),
    ("立场/阵营攻击", r"资本|水军|蹭热度|黑红|营销号|推手|带节奏|买热搜"),
]


def label_col(name: str) -> str:
    return f"lbl_{name}"


def label_feature_cols(names: list[str] | None = None) -> list[str]:
    names = names or SHAPLEY_LABEL_NAMES
    return [label_col(n) for n in names]


def label_display(name: str) -> str:
    return f"标签·{name}"


def add_label_columns(df: pd.DataFrame, names: list[str] | None = None) -> pd.DataFrame:
    out = df.copy()
    name_set = set(names) if names else {n for n, _, _ in DISCOURSE_LABELS}
    pat_map = {n: p for n, p, _ in DISCOURSE_LABELS}
    for name in name_set:
        pat = pat_map.get(name)
        if not pat:
            continue
        out[label_col(name)] = (
            out["content"].astype(str).str.contains(pat, regex=True, na=False).astype(float)
        )
    return out


def count_any_label(text: str) -> int:
    s = str(text or "")
    return sum(1 for _, pat, _ in DISCOURSE_LABELS if re.search(pat, s, re.I))


def dimension_hits(text: str) -> list[str]:
    s = str(text or "")
    hits = [dim for dim, pat in _DIM_PATTERNS if re.search(pat, s, re.I)]
    return list(dict.fromkeys(hits))


def classify_dimension(text: str) -> str:
    hits = dimension_hits(text)
    if not hits:
        return "其他/综合"
    if len(hits) == 1:
        return hits[0]
    return hits[0]

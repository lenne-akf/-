from __future__ import annotations
# -*- coding: utf-8
"""699 粉籍子样本 · Logistic 共享特征与数据框。"""

import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import COMMENTS_TOPICS, FENJI_CSV, bootstrap_sys_path
from event_phases import OUTBREAK_END, OUTBREAK_START

bootstrap_sys_path()
from build_topic_escalator import ATTACK_LEXICON  # noqa: E402

FONT = "Microsoft YaHei, SimHei, PingFang SC, sans-serif"
VIZ_W = 1920
LAYER_COLORS = {"结构层": "#5c4a1e", "主体层": "#A67C52", "话语层": "#B03A3A"}

FENJI_COLS = ["fenji_shan", "fenji_li", "cross_fenji"]
DISCOURSE_COLS = ["neg_emotion", "is_template", "attack_lexicon", "log_text_len"]

FEATURE_META = {
    "phase_burst": ("爆发阶段", "结构层"),
    "fenji_shan": ("单依纯粉籍", "主体层"),
    "fenji_li": ("李荣浩粉籍", "主体层"),
    "cross_fenji": ("跨界粉籍", "主体层"),
    "neg_emotion": ("消极情感", "话语层"),
    "is_template": ("模板化攻击", "话语层"),
    "attack_lexicon": ("攻击词命中", "话语层"),
    "log_text_len": ("评论长度(log)", "话语层"),
}

_RE_TEMPLATE = re.compile(
    r"又如何呢|又能怎|如何呢|支持维权|尊重原创|绝不姑息|"
    r"李荣浩全肯定|守护原创|墙倒众人推",
    re.I,
)


def _hex_rgba(hex_color: str, alpha: float = 0.85) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _in_burst(created_at: str) -> float:
    s = str(created_at or "")[:10]
    if not s:
        return 0.0
    return 1.0 if OUTBREAK_START <= s <= OUTBREAK_END else 0.0


def _attack_lexicon_hits(text: str) -> float:
    s = str(text or "")
    return float(sum(1 for w in ATTACK_LEXICON if w in s))


def analysis_frame() -> pd.DataFrame:
    if not FENJI_CSV.exists():
        raise FileNotFoundError(f"缺少粉籍表: {FENJI_CSV}")
    fenji = pd.read_csv(FENJI_CSV, dtype={"user_id": str})
    fenji = fenji.rename(columns={"fenji": "fandom_label"})
    raw = pd.read_csv(COMMENTS_TOPICS, dtype={"user_id": str, "comment_id": str})
    raw = raw[raw["platform"] == "weibo"].copy()
    raw = raw[raw["user_id"].isin(set(fenji["user_id"].astype(str)))]
    raw["topic_id"] = pd.to_numeric(raw["topic_id"], errors="coerce").fillna(-1).astype(int)
    raw["y_alien"] = raw["topic_id"].isin([4, 5]).astype(int)
    raw = raw.merge(fenji[["user_id", "fandom_label"]], on="user_id", how="left")

    lab = raw["fandom_label"].astype(str)
    raw["fenji_shan"] = lab.str.contains("单依纯", na=False).astype(float)
    raw["fenji_li"] = lab.str.contains("李荣浩", na=False).astype(float)
    raw["cross_fenji"] = ((raw["fenji_shan"] + raw["fenji_li"]) >= 1).astype(float)
    raw["phase_burst"] = raw["created_at"].map(_in_burst)
    raw["neg_emotion"] = (pd.to_numeric(raw.get("sentiment_score", 0.5), errors="coerce").fillna(0.5) < 0.35).astype(float)
    raw["is_template"] = raw["content"].astype(str).str.contains(_RE_TEMPLATE, regex=True, na=False).astype(float)
    raw["attack_lexicon"] = raw["content"].map(_attack_lexicon_hits).clip(0, 5) / 5.0
    raw["log_text_len"] = raw["content"].astype(str).str.len().map(lambda x: math.log1p(x) / 8.0)
    return raw


def layer_summary(coef_df: pd.DataFrame) -> pd.DataFrame:
    if coef_df.empty or "layer" not in coef_df.columns:
        return pd.DataFrame()
    out = coef_df.groupby("layer", as_index=False)["abs_coef"].sum()
    total = out["abs_coef"].sum() or 1.0
    out["pct"] = (100.0 * out["abs_coef"] / total).round(1)
    return out

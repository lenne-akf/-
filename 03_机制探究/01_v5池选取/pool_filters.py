from __future__ import annotations
# -*- coding: utf-8 -*-
"""escalator/簇4 池评论过滤：仅保留可识别 user_id（微博数据2）。"""
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from _paths import OUT, DATA, OVERVIEW, COMMENTS_TOPICS, SENTIMENT, V5_USER_IDS, FENJI_CSV, bootstrap_sys_path
bootstrap_sys_path()


import pandas as pd


def valid_user_id_mask(series: pd.Series) -> pd.Series:
    return (
        series.notna()
        & (series.astype(str).str.strip() != "")
        & (series.astype(str) != "nan")
    )


def pool_user_ids(fenji: pd.DataFrame, column: str = "user_id") -> set[str]:
    return set(fenji.loc[valid_user_id_mask(fenji[column]), column].astype(str))


def filter_pool_comments(raw: pd.DataFrame, pool_uids: set[str]) -> pd.DataFrame:
    clean_pool = {str(u) for u in pool_uids if str(u).strip() not in ("", "nan") and pd.notna(u)}
    return raw[
        valid_user_id_mask(raw["user_id"])
        & raw["user_id"].astype(str).isin(clean_pool)
    ].copy()
